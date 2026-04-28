from datetime import datetime, timedelta, timezone
from tools.auth import get_google_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def list_events(days_ahead: int = 7, max_results: int = 10) -> dict:
    service = get_google_service("calendar", "v3")
    result = service.events().list(
        calendarId="primary",
        timeMin=_now_iso(),
        timeMax=_future_iso(days_ahead),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    raw_events = result.get("items", [])
    events = []
    for e in raw_events:
        start = e.get("start", {})
        end = e.get("end", {})
        events.append({
            "id": e["id"],
            "title": e.get("summary", "(No title)"),
            "start": start.get("dateTime", start.get("date", "")),
            "end": end.get("dateTime", end.get("date", "")),
            "description": e.get("description", ""),
            "location": e.get("location", ""),
        })

    return {"count": len(events), "events": events}


def create_event(
    title: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    timezone: str = "UTC",
) -> dict:
    service = get_google_service("calendar", "v3")
    body = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {"dateTime": start, "timeZone": timezone},
        "end": {"dateTime": end, "timeZone": timezone},
    }
    event = service.events().insert(calendarId="primary", body=body).execute()
    return {
        "event_id": event["id"],
        "title": event.get("summary", ""),
        "start": event.get("start", {}).get("dateTime", ""),
        "status": "created",
    }


def update_event(
    event_id: str,
    title: str = None,
    start: str = None,
    end: str = None,
    description: str = None,
) -> dict:
    service = get_google_service("calendar", "v3")
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()

    patch = {}
    if title is not None:
        patch["summary"] = title
    if description is not None:
        patch["description"] = description
    if start is not None:
        tz = existing.get("start", {}).get("timeZone", "UTC")
        patch["start"] = {"dateTime": start, "timeZone": tz}
    if end is not None:
        tz = existing.get("end", {}).get("timeZone", "UTC")
        patch["end"] = {"dateTime": end, "timeZone": tz}

    service.events().patch(calendarId="primary", eventId=event_id, body=patch).execute()
    return {"event_id": event_id, "status": "updated"}


def delete_event(event_id: str) -> dict:
    service = get_google_service("calendar", "v3")
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return {"event_id": event_id, "status": "deleted"}
