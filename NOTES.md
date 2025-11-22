Local setup snapshot

- Calendars in use:
  - primary: laprice90@gmail.com
  - work: 8e22e5f7569a8c2b8104ac425a23a232eae1e3eecc3f3d06a96f83aa2ec76a95@group.calendar.google.com
  - family: a66a6799c78d408ccb4051ff0359ab3bd2fe276f04982b816b6349ecddb53b0c@group.calendar.google.com
  - food: fgdud7v553abqa2i8o0bt4vac8@group.calendar.google.com
  - chores: e602ac0d8d4a91a53c59ccf2e6e9a0fe9154755737c507492b07f008065f0d2e@group.calendar.google.com
  - hobbies: bb167916bbd1f470aed1fe96685b9125967777dc79004a6e34a553575d6f990b@group.calendar.google.com
  - notes (info-only): b6e7902ce9bc252ae19c49838140331a8872f3effcd9ac435dc4fdf342f87ed6@group.calendar.google.com (color: graphite/8)

- Recurring events created directly in Google Calendar:
  - Drop Louis to school: Mon–Wed, 08:45–09:15, on Family calendar (id: l855has7g99gicls2qo84j5g68)
  - Louis Rugby: Mondays, 17:00–18:00, on Family calendar (existing recurring series)
  - Louis Squirrels (info only, non-blocking): Thursdays, 17:00–18:00, on Notes calendar, transparent, id: ecte7v2i9g1607l7cf5jmlkot4
  - Louis Swimming: Fridays, 17:30–18:00, on Family calendar, id: c3vknlevs511r9sjivpbn81e84
  - Pick up Sarah and Louis for rugby: Mondays, 16:20–17:00, on Primary calendar, id: h70sidi1q10c8b2uipa34t3oe4

- DAW/Music studies:
  - Lesson plan: refs/Music Studies/Plan
  - Progress log: refs/Music Studies/Progress.md
  - Schedule DAW sessions manually on Hobbies; skip if away. After each session, log what you did in Progress.md so the next week knows where to resume.
  - Baseline (manual each week, adjust around conflicts):
    - DAW study: Tue–Fri ~16:15–17:30 on Hobbies (Stage plan in Plan file). Place ad hoc each week; do not auto-repeat.
    - Piano practice: Daily ~19:45–20:05 on Hobbies. Place manually each week; okay to skip if away.
    - Music theory: Two 30m sessions per week (e.g., Sat/Sun 09:00–09:30) on Hobbies. Place manually each week; adjust/skip if away.
  - Evening cutoff: no productive tasks after 20:05; keep time after 20:05 clear for downtime.

- Blueprint/config files:
  - schedule_config.json: editable template for work hours, meals, fixed events, hobby windows, calendar map, overrides.
  - build_week.py: reads the config, builds a plan for a target week, dry-run by default; use --push to create events.
  - list_events.py: lists events (with notes) across mapped calendars for a given window.
