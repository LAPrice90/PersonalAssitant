"""
Create a Google Tasks shopping list from a shopping JSON.

Usage:
  python shopping_client.py shopping_example.json
"""

import json
import sys
from typing import Any, Dict, List

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/tasks"]


def load_shopping(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def tasks_service():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    return build("tasks", "v1", credentials=creds)


def ensure_tasklist(service, title: str) -> str:
    existing = service.tasklists().list(maxResults=100).execute().get("items", [])
    for tl in existing:
        if tl.get("title") == title:
            return tl["id"]
    created = service.tasklists().insert(body={"title": title}).execute()
    return created["id"]


def build_title(item: Dict[str, Any]) -> str:
    aisle = item.get("aisle", "misc")
    name = item.get("name")
    packs = item.get("packs")
    pack_size = item.get("pack_size")
    qty = item.get("qty")
    unit = item.get("unit")
    parts = [f"{aisle} – {name}"]
    detail = []
    if qty and unit:
        detail.append(f"need {qty} {unit}")
    if packs and pack_size:
        detail.append(f"buy {packs} x {pack_size}")
    elif packs:
        detail.append(f"buy {packs}")
    if detail:
        parts.append(f"({' | '.join(detail)})")
    return " ".join(parts)


def build_notes(item: Dict[str, Any]) -> str:
    bits: List[str] = []
    if item.get("notes"):
        bits.append(str(item["notes"]))
    if item.get("est_cost"):
        bits.append(f"est_cost: {item['est_cost']}")
    return "\n".join(bits)


def create_tasks(service, tasklist_id: str, items: List[Dict[str, Any]]) -> None:
    for item in items:
        service.tasks().insert(
            tasklist=tasklist_id,
            body={
                "title": build_title(item),
                "notes": build_notes(item) or None,
            },
        ).execute()


def main():
    if len(sys.argv) < 2:
        print("Usage: python shopping_client.py shopping_example.json")
        sys.exit(1)
    data = load_shopping(sys.argv[1])
    week = data.get("week", "Shopping")
    items = data.get("shopping", [])
    if not items:
        print("No shopping items found.")
        sys.exit(0)
    svc = tasks_service()
    tl_id = ensure_tasklist(svc, f"Shopping List ({week})")
    create_tasks(svc, tl_id, items)
    print(f"Created tasks in list: Shopping List ({week})")


if __name__ == "__main__":
    main()
