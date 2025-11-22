"""
Lightweight Google Tasks helper.

Scopes required: https://www.googleapis.com/auth/tasks
Token from auth_gcal.py must include that scope.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

import gcal_client

TASKS_SCOPE = ["https://www.googleapis.com/auth/tasks"]


def _service() -> Any:
    creds = Credentials.from_authorized_user_file("token.json", TASKS_SCOPE)
    return build("tasks", "v1", credentials=creds)


def list_tasklists() -> List[Dict[str, Any]]:
    svc = _service()
    return svc.tasklists().list(maxResults=100).execute().get("items", [])


def ensure_tasklist(title: str) -> str:
    svc = _service()
    existing = [tl for tl in list_tasklists() if tl.get("title") == title]
    if existing:
        return existing[0]["id"]
    created = svc.tasklists().insert(body={"title": title}).execute()
    return created["id"]


def list_tasks(tasklist_id: str, show_completed: bool = False) -> List[Dict[str, Any]]:
    svc = _service()
    params: Dict[str, Any] = {
        "tasklist": tasklist_id,
        "maxResults": 200,
        "showCompleted": show_completed,
        "showHidden": show_completed,
        "showDeleted": False,
    }
    resp = svc.tasks().list(**params).execute()
    return resp.get("items", [])


def add_task(
    tasklist_id: str,
    title: str,
    notes: Optional[str] = None,
    due: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    svc = _service()
    body: Dict[str, Any] = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return svc.tasks().insert(tasklist=tasklist_id, body=body).execute()


def complete_task(tasklist_id: str, task_id: str) -> Dict[str, Any]:
    svc = _service()
    return svc.tasks().patch(tasklist=tasklist_id, task=task_id, body={"status": "completed"}).execute()


def add_task_with_block(
    tasklist_id: str,
    title: str,
    calendar_id: Optional[str] = None,
    start: Optional[dt.datetime] = None,
    end: Optional[dt.datetime] = None,
    notes: Optional[str] = None,
    block_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Google Task (checkbox) and, if calendar_id/start/end provided, create a linked calendar block.
    Returns dict with task and event ids.
    """
    task = add_task(tasklist_id, title, notes=notes, due=None)
    event = None
    if calendar_id and start and end:
        ext = {"linked_task_id": task.get("id"), "linked_tasklist_id": tasklist_id, "category": "tasks", "source": "task_block"}
        event = gcal_client.create_event(
            calendar_id=calendar_id,
            summary=title,
            start=start,
            end=end,
            description=block_description or notes,
            extended_properties=ext,
        )
    return {"task": task, "event": event}
