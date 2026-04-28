import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from tools.auth import get_google_service


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def list_inbox(max_results: int = 10, query: str = "") -> dict:
    service = get_google_service("gmail", "v1")
    params = {"userId": "me", "labelIds": ["INBOX"], "maxResults": max_results}
    if query:
        params["q"] = query

    result = service.users().messages().list(**params).execute()
    raw_messages = result.get("messages", [])

    messages = []
    for msg in raw_messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = detail.get("payload", {}).get("headers", [])
        messages.append({
            "id": msg["id"],
            "from": _get_header(headers, "From"),
            "subject": _get_header(headers, "Subject"),
            "date": _get_header(headers, "Date"),
            "snippet": detail.get("snippet", ""),
        })

    return {"count": len(messages), "messages": messages}


def search_emails(query: str, max_results: int = 10) -> dict:
    service = get_google_service("gmail", "v1")
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    raw_messages = result.get("messages", [])

    messages = []
    for msg in raw_messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = detail.get("payload", {}).get("headers", [])
        messages.append({
            "id": msg["id"],
            "from": _get_header(headers, "From"),
            "subject": _get_header(headers, "Subject"),
            "date": _get_header(headers, "Date"),
            "snippet": detail.get("snippet", ""),
        })

    return {"count": len(messages), "messages": messages}


def send_email(to: str, subject: str, body: str) -> dict:
    service = get_google_service("gmail", "v1")
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return {"message_id": sent["id"], "status": "sent"}


def create_draft(to: str, subject: str, body: str) -> dict:
    service = get_google_service("gmail", "v1")
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return {"draft_id": draft["id"], "status": "draft_created"}
