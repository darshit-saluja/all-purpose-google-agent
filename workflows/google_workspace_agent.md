# Google Workspace Agent — Standard Operating Procedure

## Objective

Orchestrate Google Workspace actions (Gmail, Calendar, Sheets, YouTube) via natural language chat. Parse user intent, dispatch the correct tool, interpret the result, and return a helpful plain-text response.

## Required Inputs

- Valid `token.json` in the project root (created on first run via OAuth browser flow)
- `KIE_AI_API_KEY` set in `.env`
- `FLASK_SECRET_KEY` set in `.env`
- User's natural language message

## How the Dispatch Loop Works

1. User sends a message via the chat UI.
2. Flask appends it to the in-memory session history.
3. The full history + system prompt is sent to the AI (claude-haiku-4-5 via kie.ai).
4. If the AI responds with a JSON `{"action": "...", "params": {...}}` object, the corresponding tool is executed and the result is appended as a `TOOL_RESULT:` message.
5. The AI is called again with the updated history to produce a plain-text summary.
6. The final plain-text reply is returned to the frontend.
7. Maximum 5 iterations per user message to prevent infinite loops.

## Intent Detection Keywords

| Service   | Keywords |
|-----------|----------|
| Gmail     | email, inbox, send, draft, message, unread, from, subject, reply |
| Calendar  | event, meeting, schedule, appointment, calendar, invite, reminder |
| Sheets    | spreadsheet, sheet, row, cell, range, data, append, update, table |
| YouTube   | video, channel, watch, search YouTube, my videos, views, likes |

## Available Actions

| Action                  | Required Params                           | Optional Params                      |
|-------------------------|-------------------------------------------|--------------------------------------|
| `gmail_list_inbox`      | —                                         | `max_results`, `query`               |
| `gmail_search`          | `query`                                   | `max_results`                        |
| `gmail_send`            | `to`, `subject`, `body`                   | —                                    |
| `gmail_create_draft`    | `to`, `subject`, `body`                   | —                                    |
| `calendar_list_events`  | —                                         | `days_ahead`, `max_results`          |
| `calendar_create_event` | `title`, `start`, `end`                   | `description`, `location`, `timezone`|
| `calendar_update_event` | `event_id`                                | `title`, `start`, `end`, `description`|
| `calendar_delete_event` | `event_id`                                | —                                    |
| `sheets_read_range`     | `spreadsheet_id`, `range_notation`        | —                                    |
| `sheets_append_row`     | `spreadsheet_id`, `sheet_name`, `values`  | —                                    |
| `sheets_update_cell`    | `spreadsheet_id`, `cell_notation`, `value`| —                                    |
| `youtube_search`        | `query`                                   | `max_results`, `order`               |
| `youtube_my_videos`     | —                                         | `max_results`                        |

## Default Parameter Values

| Param         | Default |
|---------------|---------|
| `max_results` | 10      |
| `days_ahead`  | 7       |
| `timezone`    | UTC     |

## When to Ask for Clarification (Do Not Guess)

- **`calendar_create_event`**: If start or end time is not specified, ask before calling. Always use ISO8601 format (e.g. `2026-04-29T10:00:00`).
- **`gmail_send`**: If the recipient (`to`) or subject was not explicitly stated by the user, confirm before sending. Sending is irreversible.
- **`calendar_delete_event`** and **`calendar_update_event`**: Always confirm the event with the user before acting. Show the event title and time, then ask for confirmation.
- **Sheets operations**: If no spreadsheet ID is present in the message, ask the user to paste the spreadsheet URL or ID. The ID is the long string in the URL: `docs.google.com/spreadsheets/d/<ID>/edit`.

## Multi-Step Task Patterns

**Example 1 — Summarize and send:**
> "Send a summary of my unread emails to alice@example.com"
1. `gmail_list_inbox` with `query: "is:unread"`
2. Generate a summary from the TOOL_RESULT
3. Ask user to confirm recipient + subject before calling `gmail_send`

**Example 2 — Scheduled event from context:**
> "Schedule a follow-up meeting with Bob for next Tuesday at 3pm"
1. Determine the date from context (today is available in the system prompt)
2. If time zone not mentioned, use UTC and note this to the user
3. `calendar_create_event`

**Example 3 — Read then update:**
> "Check what's in Sheet1 row 5 and update cell B5 to 'Done'"
1. `sheets_read_range` with `range_notation: "Sheet1!A5:Z5"`
2. Report result, then `sheets_update_cell` with `cell_notation: "Sheet1!B5"`, `value: "Done"`

## Output Format Rules

1. After receiving a `TOOL_RESULT`, always respond in plain English. Never return raw JSON to the user.
2. **Emails**: Show a numbered list with From, Subject, Date, and one-line snippet per email.
3. **Calendar events**: Show Title, Date/Time (human-readable), and Location if present.
4. **Sheets data**: Describe what was read or written in a sentence; include row count.
5. **YouTube search**: Show Title, Channel, and full URL per result.
6. **YouTube my videos**: Show Title, Views, Likes, and URL.
7. Never expose raw internal IDs (message ID, event ID, draft ID) unless the user explicitly asks.
8. Keep responses concise. Use bullet points or numbered lists for multi-item results.

## Confirmation Flow (Destructive Actions)

For `gmail_send`, `calendar_delete_event`, and `calendar_update_event`:

1. State what action you're about to take (e.g. "I'm about to send an email to bob@example.com with subject 'Meeting notes'. Shall I proceed?")
2. Wait for the user to confirm (e.g. "yes", "go ahead", "send it")
3. Only then emit the JSON action

## Error Recovery

| Situation | Response |
|---|---|
| Unknown action in registry | "I don't have a tool for that yet." |
| Tool execution error (generic) | Report the error plainly. Offer to retry or approach differently. |
| `token.json` expired / invalid | "Your Google session has expired. Please delete `token.json` from the project folder and restart the app to re-authenticate." |
| API quota exceeded (HTTP 429 from Google) | "Google API quota exceeded. Please wait a few minutes before trying again." |
| No spreadsheet ID provided | Ask for the Google Sheets URL |
| Ambiguous request | Ask one targeted clarifying question. Do not make assumptions. |
| Rate limit from kie.ai (HTTP 429) | "I'm being rate limited. Please wait 60 seconds and try again." |

## Self-Improvement Notes

_(Add entries below as new edge cases or API quirks are discovered in production)_

- `youtube_search` supports an optional `order` param. Pass `order="date"` when the user asks for the "latest", "newest", or "most recent" video. Leave it out (defaults to `"relevance"`) for general searches. YouTube's relevance ranking is engagement-based, so a popular older video will beat a brand-new one — always pass `order="date"` for recency intent. Other accepted values: `"rating"`, `"viewCount"`, `"title"`.
- `youtube_my_videos` requires the authenticated account to have a YouTube channel. If the user has no channel, the API returns an empty items list — handle gracefully.
- Gmail `messages.get` with `format="metadata"` does not return the email body. If users ask for full email content, a `format="full"` call with MIME parsing will be needed (not yet implemented).
- Calendar datetimes must include timezone info or Google rejects the request. Default to UTC and tell the user if their timezone was assumed.
- Sheets `append_row` with `insertDataOption="INSERT_ROWS"` always inserts below the last row with data, not at a fixed position. Inform users if they expect row-number control.
