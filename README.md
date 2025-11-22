# Google Calendar + Tasks Starter

Helpers for Google Calendar and Google Tasks, plus planning tools.

## Setup
- Put `credentials.json` in the repo root (keep it out of git).
- Install deps: `pip install -r requirements.txt`
- Run auth to create `token.json` (Calendar + Tasks scopes):
  ```bash
  python auth_gcal.py
  ```
  Approve in the browser; `token.json` is saved next to `credentials.json`.

## Scripts/helpers
- `gcal_client.py`: list/create/patch calendar events.
- `tasks_client.py`: list/create tasklists, add/complete tasks, and `add_task_with_block` to mirror a task into a calendar block.
- `list_events.py`: list events (with notes/meta) across mapped calendars for a time window.
- `plan_week.py`: read-only planner; prints busy items for a target week across mapped calendars. No writes.
- Config: `schedule_config.json` holds calendar IDs/timezone.

## Quick examples
- List calendars:
  ```python
  import gcal_client
  print(gcal_client.list_calendars())
  ```
- Create an event:
  ```python
  import datetime as dt, gcal_client
  start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
  end = start + dt.timedelta(hours=1)
  ev = gcal_client.create_event("primary", "Test event", start, end, description="Hello world")
  print(ev["htmlLink"])
  ```
- Create a task + optional calendar block:
  ```python
  import datetime as dt, tasks_client
  tl = tasks_client.ensure_tasklist("Daily Tasks")
  start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
  end = start + dt.timedelta(minutes=30)
  res = tasks_client.add_task_with_block(
      tasklist_id=tl,
      title="Test task",
      notes="Checkbox + time block",
      calendar_id="your-calendar-id",  # omit to skip calendar block
      start=start,
      end=end,
  )
  print(res)
  ```
- Read-only weekly busy view:
  ```bash
  python plan_week.py            # next week
  python plan_week.py --week 2025-W48
  ```

## Notes
- `token.json` auto-refreshes; rerun `auth_gcal.py` if you revoke access.
- Times should include timezone (e.g., Europe/London). Use category→calendar mapping in `schedule_config.json` for routing.
