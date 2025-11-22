Calendar entry conventions

- Calendars by category
  - work: work blocks, deep work, admin.
  - family: kid logistics you drive/attend (school run, swimming, rugby) and family events.
  - food: meals (breakfast/lunch/dinner) and food prep/travel.
  - chores: house chores/errands you do.
  - hobbies: intentional hobby windows/sessions.
  - notes: informational/non-blocking items (set transparency=transparent).
  - primary: general personal items when no category fits; avoid using primary for tasks/notes.

- DAW/Music studies
  - Schedule manually, ad hoc, on the Hobbies calendar; skip if away—do not auto-reschedule.
  - Lesson content/order lives in `refs/Music Studies/Plan` (Stage/Session list).
  - After each session, append what you did to `refs/Music Studies/Progress.md` so the next week picks up the right lesson.

- Recurring vs. one-off
  - If it happens most weeks: make it a recurring series in the correct calendar.
  - If you need an exception: edit/delete that occurrence only; keep the series.
  - Info-only recurring items (you don’t attend): put on Notes and set transparency=transparent.

- Naming and metadata
  - Summary: clear verb + object (e.g., “Drop Louis to school”, “Work block”, “Hobby window”).
  - Add description if instructions/recipes/addresses matter.
  - When creating via scripts, add extendedProperties.private:
    - category: one of work/family/food/chores/hobbies/notes/primary
    - source: setup/plan/manual
    - plan_id: if from a weekly build

- Times and timezone
  - Use Europe/London with explicit dateTime (not all-day) for anything time-bound.
  - For non-blocking info items, also set transparency=transparent.

- Scheduling rules
  - Pull live calendars before placing new events (free/busy across all mapped calendars).
  - Honor buffers (default 10m) and avoid placing over busy events.
  - Max block length: 2h (adjust in schedule_config.json if needed).
  - Earliest task start: 08:00; latest: 20:00 (adjust in schedule_config.json).

- Files/scripts
  - schedule_config.json: blueprint for work hours, meals, fixed events, hobby windows, calendar map, overrides.
  - build_week.py: builds weekly plan; dry-run by default; use --push to create events with metadata.
  - list_events.py: list events (with notes) across calendars for a window.
  - NOTES.md: current calendar IDs and key recurring events.
