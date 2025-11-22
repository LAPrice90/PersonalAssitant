"""
Plan helper: pull live events for a target week and print busy windows.
No events are created. Use this before scheduling to avoid conflicts.

Usage:
  .venv\\Scripts\\python.exe plan_week.py           # default next week
  .venv\\Scripts\\python.exe plan_week.py --week 2025-W48
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Tuple

from zoneinfo import ZoneInfo

import gcal_client

CONFIG_PATH = Path("schedule_config.json")


def iso_week_start(iso_week: str) -> dt.date:
    year, week = iso_week.split("-W")
    return dt.datetime.strptime(f"{year} {int(week)} 1", "%G %V %u").date()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def list_events(cal_ids: Dict[str, str], start: dt.datetime, end: dt.datetime) -> List[Tuple[str, dict]]:
    rows: List[Tuple[str, dict]] = []
    for name, cal_id in cal_ids.items():
        events = gcal_client.list_events(calendar_id=cal_id, time_min=start, time_max=end, max_results=400)
        for ev in events:
            rows.append((name, ev))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan helper: list busy windows for a week (no writes)")
    parser.add_argument("--week", help="ISO week YYYY-Www; default next week")
    args = parser.parse_args()

    cfg = load_config(CONFIG_PATH)
    tz = ZoneInfo(cfg.get("timezone", "UTC"))

    today = dt.date.today()
    if args.week:
        week_start = iso_week_start(args.week)
    else:
        monday = today - dt.timedelta(days=today.weekday())
        week_start = monday + dt.timedelta(days=7)

    window_start = dt.datetime.combine(week_start, dt.time.min, tzinfo=tz)
    window_end = window_start + dt.timedelta(days=7)

    cal_ids = cfg["calendar_map"]
    events = list_events(cal_ids, window_start, window_end)

    # Sort by start time
    def start_dt(ev: dict) -> str:
        return ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or ""

    events.sort(key=lambda x: start_dt(x[1]))

    print(f"Week: {week_start} to {week_start + dt.timedelta(days=6)} ({window_start.isoformat()} to {window_end.isoformat()})")
    print(f"Timezone: {cfg.get('timezone', 'UTC')}")
    print(f"Calendars: {', '.join(cal_ids.keys())}")
    print("\nBusy items:")
    if not events:
        print("  None")
        return
    for cal_name, ev in events:
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        summary = ev.get("summary") or "(no title)"
        desc = ev.get("description") or ""
        ext = ev.get("extendedProperties", {}).get("private") if ev.get("extendedProperties") else None
        meta = []
        if ext:
            for k, v in ext.items():
                meta.append(f"{k}={v}")
        meta_str = "; ".join(meta) if meta else ""
        print(f"- [{cal_name}] {summary} | {start} -> {end}")
        if desc:
            print(f"    desc: {desc[:200].replace('\\n', ' ')}{'...' if len(desc)>200 else ''}")
        if meta_str:
            print(f"    meta: {meta_str}")


if __name__ == "__main__":
    main()
