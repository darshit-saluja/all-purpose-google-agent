import os
import json
import uuid
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from tools import gmail_tools, calendar_tools, sheets_tools, youtube_tools
from tools.auth import check_auth_status

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", str(uuid.uuid4()))

KIE_AI_ENDPOINT = "https://api.kie.ai/claude/v1/messages"
MAX_TOOL_ITERATIONS = 5

TOOL_REGISTRY = {
    "gmail_list_inbox":      gmail_tools.list_inbox,
    "gmail_search":          gmail_tools.search_emails,
    "gmail_send":            gmail_tools.send_email,
    "gmail_create_draft":    gmail_tools.create_draft,
    "calendar_list_events":  calendar_tools.list_events,
    "calendar_create_event": calendar_tools.create_event,
    "calendar_update_event": calendar_tools.update_event,
    "calendar_delete_event": calendar_tools.delete_event,
    "sheets_read_range":     sheets_tools.read_range,
    "sheets_append_row":     sheets_tools.append_row,
    "sheets_update_cell":    sheets_tools.update_cell,
    "youtube_search":        youtube_tools.search_videos,
    "youtube_my_videos":     youtube_tools.list_my_videos,
}

SYSTEM_PROMPT = """You are a Google Workspace AI assistant controlling Gmail, Google Calendar, Google Sheets, and YouTube.

CRITICAL: Do NOT use any tools, bash commands, or code execution. Only respond with plain text OR a single JSON object.

ACTION DISPATCH: When the user wants you to perform a Workspace action, respond with ONLY a raw JSON object (no markdown fences, no extra text):
{"action": "<name>", "params": {...}}

Available actions:
- gmail_list_inbox (max_results, query)
- gmail_search (query, max_results)
- gmail_send (to, subject, body)
- gmail_create_draft (to, subject, body)
- calendar_list_events (days_ahead, max_results)
- calendar_create_event (title, start, end, description, location, timezone)
- calendar_update_event (event_id, title, start, end, description)
- calendar_delete_event (event_id)
- sheets_read_range (spreadsheet_id, range_notation)
- sheets_append_row (spreadsheet_id, sheet_name, values)
- sheets_update_cell (spreadsheet_id, cell_notation, value)
- youtube_search (query, max_results)
- youtube_my_videos (max_results)

Rules:
0. NEVER send acknowledgment, planning, or intermediate messages before executing tools. If ANY tool call is needed to fulfill the request, your VERY FIRST response must be the raw JSON action — no preamble, no "I'll help you", no "First, let me", no "Sure!".
1. For multi-step requests: after each TOOL_RESULT, immediately dispatch the NEXT required action as JSON if more work remains. Only respond in plain text once ALL tasks in the request are fully complete. Your final plain-text reply must summarize everything accomplished (e.g. "The latest video by X is [title]. I've sent an email to Y with subject Z.").
2. Conversational messages (no action needed) get plain-text replies.
3. Confirm recipient+subject before gmail_send if not explicitly stated.
4. Confirm before calendar_delete_event.
5. Ask for spreadsheet URL/ID if none provided for Sheets.
6. Format email/event lists as numbered lists with key details.
7. Never expose raw IDs unless the user asks.
8. Use ISO8601 for calendar datetimes (e.g. 2026-04-29T17:00:00). Default timezone: UTC.
"""


def _extract_action(text: str) -> str | None:
    """Return the first JSON action block found anywhere in text, or None."""
    import re
    # Try fenced code block: ```json {...} ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\"action\".*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # Try bare JSON object containing "action" key
    bare = re.search(r'(\{[^{}]*"action"\s*:[^{}]*\})', text, re.DOTALL)
    if bare:
        return bare.group(1).strip()
    return None


def _call_ai(messages: list) -> str:
    api_key = os.getenv("KIE_AI_API_KEY")
    if not api_key:
        raise ValueError("KIE_AI_API_KEY not set in environment variables")

    # Split system message out — Anthropic format puts it as a top-level field
    system_content = None
    user_messages = []
    for m in messages:
        if m["role"] == "system":
            system_content = m["content"]
        else:
            user_messages.append(m)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5",
        "messages": user_messages,
        "max_tokens": 4096,
        "stream": False,
    }
    if system_content:
        payload["system"] = system_content

    response = requests.post(KIE_AI_ENDPOINT, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    text_blocks = [b for b in data.get("content", []) if b.get("type") == "text"]
    if not text_blocks:
        raise ValueError(f"API returned no text content. stop_reason={data.get('stop_reason')!r}, response={json.dumps(data)[:500]}")
    return text_blocks[0]["text"]


def _run_tool(action: str, params: dict) -> str:
    if action not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown action: {action}"})
    try:
        result = TOOL_REGISTRY[action](**params)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/auth/status")
def auth_status():
    return jsonify(check_auth_status())


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"reply": None, "error": "No message provided"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"reply": None, "error": "Empty message"}), 400

    # Accept conversation history from the client (stateless server pattern).
    # The client (localStorage) is the source of truth for history.
    client_history = data.get("history", [])

    # Build message list: system prompt + client history + current user message
    # Filter out system-role entries from client history for safety
    safe_history = [
        m for m in client_history
        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
    ]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + safe_history
    messages.append({"role": "user", "content": user_message})

    final_reply = None

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            raw = _call_ai(messages)

            action_json = _extract_action(raw)
            if action_json:
                try:
                    parsed = json.loads(action_json)
                    if isinstance(parsed, dict) and "action" in parsed:
                        action = parsed["action"]
                        params = parsed.get("params", {})

                        messages.append({"role": "assistant", "content": raw})

                        tool_result = _run_tool(action, params)

                        tool_msg = f"TOOL_RESULT: {tool_result}"
                        messages.append({"role": "user", "content": tool_msg})
                        continue
                except (json.JSONDecodeError, ValueError):
                    pass

            final_reply = raw
            break

        if final_reply is None:
            final_reply = raw

    except requests.exceptions.Timeout:
        return jsonify({"reply": None, "error": "AI request timed out. Please try again."})
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return jsonify({"reply": None, "error": "Rate limited. Please wait 60 seconds and try again."})
        return jsonify({"reply": None, "error": f"API error: {str(e)}"})
    except Exception as e:
        return jsonify({"reply": None, "error": str(e)})

    return jsonify({"reply": final_reply, "error": None})


@app.route("/chat/clear", methods=["POST"])
def clear_chat():
    # History is managed client-side (localStorage). This endpoint is a no-op
    # kept for frontend compatibility.
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
