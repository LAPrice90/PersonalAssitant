"""
List events across your calendars with descriptions and extended properties.

Configure CALENDAR_IDS below. By default, pulls from now for the next 7 days.
Run with your venv: `.venv\\Scripts\\python.exe list_events.py`
"""

from __future__ import annotations

import argparse
import datetime as dt
import textwrap
from typing import Dict

import gcal_client

# Map friendly names to calendarIds (edit to match your setup)
CALENDAR_IDS: Dict[str, str] = {
    "primary": "laprice90@gmail.com",
    "amazon_tasks": "8e22e5f7569a8c2b8104ac425a23a232eae1e3eecc3f3d06a96f83aa2ec76a95@group.calendar.google.com",
    "design_work": "e602ac0d8d4a91a53c59ccf2e6e9a0fe9154755737c507492b07f008065f0d2e@group.calendar.google.com",
    "family": "a66a6799c78d408ccb4051ff0359ab3bd2fe276f04982b816b6349ecddb53b0c@group.calendar.google.com",
    "food": "fgdud7v553abqa2i8o0bt4vac8@group.calendar.google.com",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="List calendar events with notes")
    parser.add_argument("--days", type=int, default=7, help="How many days ahead to pull (default: 7)")
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=args.days)

    print(f"Window: {now.isoformat()} to {end.isoformat()}")
    for name, cal_id in CALENDAR_IDS.items():
        events = gcal_client.list_events(calendar_id=cal_id, time_min=now, time_max=end, max_results=200)
        if not events:
            continue
        print(f"\n=== {name} ({cal_id}) ===")
        for ev in events:
            start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            endt = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
            summary = ev.get("summary") or "(no title)"
            desc = ev.get("description") or ""
            ext = ev.get("extendedProperties", {}).get("private") if ev.get("extendedProperties") else None
            print(f"- {summary}")
            print(f"  start: {start}  end: {endt}")
            if desc:
                wrapped = textwrap.wrap(desc, width=100)
                print("  desc:", wrapped[0])
                for line in wrapped[1:]:
                    print("        ", line)
            if ext:
                print("  meta:", ext)


if __name__ == "__main__":
    main()
