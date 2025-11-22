"""
Lightweight Google Calendar client helper.
Assumes credentials.json and token.json live in the repo root.
"""

from __future__ import annotations

import datetime as dt
import pathlib
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar"]
BASE_PATH = pathlib.Path(__file__).parent
TOKEN_PATH = BASE_PATH / "token.json"
CREDS_PATH = BASE_PATH / "credentials.json"


def _load_creds() -> Credentials:
    return Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)


def get_service():
    creds = _load_creds()
    return build("calendar", "v3", credentials=creds)


def list_calendars() -> List[Dict[str, Any]]:
    service = get_service()
    resp = service.calendarList().list().execute()
    return resp.get("items", [])


def list_events(
    calendar_id: str = "primary",
    time_min: Optional[dt.datetime] = None,
    time_max: Optional[dt.datetime] = None,
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    service = get_service()
    params: Dict[str, Any] = {
        "calendarId": calendar_id,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_min:
        params["timeMin"] = time_min.isoformat()
    if time_max:
        params["timeMax"] = time_max.isoformat()
    resp = service.events().list(**params).execute()
    return resp.get("items", [])


def create_event(
    calendar_id: str,
    summary: str,
    start: dt.datetime,
    end: dt.datetime,
    description: Optional[str] = None,
    location: Optional[str] = None,
    color_id: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    extended_properties: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    service = get_service()
    body: Dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if color_id:
        body["colorId"] = color_id
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    if extended_properties:
        body["extendedProperties"] = {"private": extended_properties}
    return service.events().insert(calendarId=calendar_id, body=body).execute()


def patch_event(calendar_id: str, event_id: str, **fields: Any) -> Dict[str, Any]:
    """
    Patch an event with arbitrary fields (e.g., summary, start/end).
    Provide start/end as RFC3339 strings or nested dicts per Google spec.
    """
    service = get_service()
    return service.events().patch(calendarId=calendar_id, eventId=event_id, body=fields).execute()
