"""
Build a weekly schedule blueprint from schedule_config.json.

By default this is a dry-run that prints the plan. Use --push to create events on Google Calendar.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

import gcal_client

CONFIG_PATH = Path("schedule_config.json")


DayKey = str  # "mon".."sun"


def iso_week_start(iso_week: str) -> dt.date:
    try:
        year, week = iso_week.split("-W")
        return dt.datetime.strptime(f"{year} {int(week)} 1", "%G %V %u").date()
    except Exception as exc:
        raise ValueError("Use ISO week format: YYYY-Www") from exc


def parse_time(timestr: str) -> dt.time:
    hour, minute = timestr.split(":")
    return dt.time(hour=int(hour), minute=int(minute))


def combine(date: dt.date, timestr: str, tz: ZoneInfo) -> dt.datetime:
    return dt.datetime.combine(date, parse_time(timestr), tzinfo=tz)


@dataclass
class PlannedEvent:
    summary: str
    start: dt.datetime
    end: dt.datetime
    category: str
    calendar_id: str
    description: Optional[str] = None
    source: str = "plan"

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "category": self.category,
            "calendar_id": self.calendar_id,
            "description": self.description,
            "source": self.source,
        }


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def day_name_to_key(day: dt.date) -> DayKey:
    return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][day.weekday()]


def within_window(ev_start: dt.datetime, ev_end: dt.datetime, win_start: dt.datetime, win_end: dt.datetime) -> bool:
    return ev_start < win_end and ev_end > win_start


def list_existing_events(calendar_ids: List[str], start: dt.datetime, end: dt.datetime) -> List[Tuple[dict, str]]:
    rows: List[Tuple[dict, str]] = []
    for cal in calendar_ids:
        events = gcal_client.list_events(calendar_id=cal, time_min=start, time_max=end, max_results=400)
        for ev in events:
            rows.append((ev, cal))
    return rows


def build_plan(config: dict, week_start: dt.date) -> List[PlannedEvent]:
    tz = ZoneInfo(config.get("timezone", "UTC"))
    cal_map: Dict[str, str] = config["calendar_map"]
    per_day_overrides: Dict[str, dict] = config.get("overrides", {}).get("per_day", {})
    per_date_overrides: Dict[str, dict] = config.get("overrides", {}).get("per_date", {})

    plan: List[PlannedEvent] = []

    for offset in range(7):
        day_date = week_start + dt.timedelta(days=offset)
        day_key = day_name_to_key(day_date)
        day_override = per_day_overrides.get(day_key, {})
        date_override = per_date_overrides.get(day_date.isoformat(), {})

        # Work hours
        work_hours = date_override.get("work_hours", day_override.get("work_hours", config.get("work_hours", {}).get(day_key)))
        if work_hours:
            start_dt = combine(day_date, work_hours["start"], tz)
            end_dt = combine(day_date, work_hours["end"], tz)
            plan.append(
                PlannedEvent(
                    summary="Work block (needs filling)",
                    start=start_dt,
                    end=end_dt,
                    category="work",
                    calendar_id=cal_map.get("primary", cal_map[list(cal_map.keys())[0]]),
                    source="plan",
                )
            )

        # Meals
        for meal in config.get("meals", []):
            start_dt = combine(day_date, meal["start"], tz)
            end_dt = combine(day_date, meal["end"], tz)
            category = meal.get("category", "food")
            plan.append(
                PlannedEvent(
                    summary=meal["name"],
                    start=start_dt,
                    end=end_dt,
                    category=category,
                    calendar_id=cal_map.get(category, cal_map.get("food", cal_map["primary"])),
                    source="meal",
                )
            )

        # Fixed events
        for fixed in config.get("fixed_events", []):
            if fixed.get("day") != day_key:
                continue
            start_dt = combine(day_date, fixed["start"], tz)
            end_dt = combine(day_date, fixed["end"], tz)
            category = fixed.get("category", "primary")
            plan.append(
                PlannedEvent(
                    summary=fixed["name"],
                    start=start_dt,
                    end=end_dt,
                    category=category,
                    calendar_id=cal_map.get(category, cal_map["primary"]),
                    source="fixed",
                )
            )

        # Hobby windows
        for hw in config.get("hobby_windows", []):
            if hw.get("day") != day_key:
                continue
            start_dt = combine(day_date, hw["start"], tz)
            end_dt = combine(day_date, hw["end"], tz)
            category = hw.get("category", "hobbies")
            plan.append(
                PlannedEvent(
                    summary="Hobby window",
                    start=start_dt,
                    end=end_dt,
                    category=category,
                    calendar_id=cal_map.get(category, cal_map["primary"]),
                    source="hobby_window",
                )
            )

    plan.sort(key=lambda e: e.start)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a weekly plan from schedule_config.json")
    parser.add_argument("--week", help="ISO week, e.g. 2025-W48. Defaults to next week.")
    parser.add_argument("--push", action="store_true", help="Create events on Google Calendar (default is dry-run)")
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    today = dt.date.today()
    if args.week:
        week_start = iso_week_start(args.week)
    else:
        # default to next week (Monday)
        monday = today - dt.timedelta(days=today.weekday())
        week_start = monday + dt.timedelta(days=7)

    tz = ZoneInfo(config.get("timezone", "UTC"))
    window_start = dt.datetime.combine(week_start, dt.time.min, tzinfo=tz)
    window_end = window_start + dt.timedelta(days=7)

    print(f"Week start: {week_start} ({window_start.isoformat()} to {window_end.isoformat()})")
    plan = build_plan(config, week_start)

    # Existing events for awareness
    cal_ids = list({config["calendar_map"][k] for k in config["calendar_map"]})
    existing = list_existing_events(cal_ids, window_start, window_end)

    print(f"\nExisting events in window: {len(existing)}")
    for ev, cal in sorted(existing, key=lambda x: x[0].get("start", {}).get("dateTime", "")):
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        print(f"[{cal}] {ev.get('summary')} | {start} -> {end}")

    print(f"\nPlanned events (dry-run, total {len(plan)}):")
    for pe in plan:
        print(f"[{pe.category}] {pe.summary} | {pe.start.isoformat()} -> {pe.end.isoformat()} | cal={pe.calendar_id}")

    if not args.push:
        print("\nDry-run only. Use --push to create these events.")
        return

    plan_id = f"plan-{week_start.isoformat()}"
    created = 0
    for pe in plan:
        body_ext = {"source": pe.source, "category": pe.category, "plan_id": plan_id}
        gcal_client.create_event(
            calendar_id=pe.calendar_id,
            summary=pe.summary,
            start=pe.start,
            end=pe.end,
            description=pe.description,
            extended_properties=body_ext,
        )
        created += 1
    print(f"\nPushed {created} events to Google Calendar.")


if __name__ == "__main__":
    main()
