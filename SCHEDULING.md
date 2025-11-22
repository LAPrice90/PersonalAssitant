# Meal Scheduling Rules (apply every week)

1) Pull live events first
- Use `plan_week.py` (or Calendar API) to pull the target week’s events. Avoid placing meals where there are outings or existing meals.

2) Slots
- Default times: Breakfast 07:00, Lunch 12:00, Dinner 18:00. Duration should cover prep + 30 min eating (e.g., 60-minute slots if prep is ~30 min).
- Evening cutoff: no productive tasks after 20:05.

Quick guardrails
- Ingredients: raw/unprepped only. All chopping/mincing/sizing and “can share a bowl” instructions go in Mise en place.
- Steps: numbered, with inline quantities. Notes for GF/pregnancy/spice/leftovers/use-up in the Notes section.

3) Placement logic
- Breakfast: rotate favorites; no single breakfast >2x/week. Sarah swap from Turkish eggs to yoghurt/fruit or poached eggs on toast. Fruits: raspberries/blueberries/banana. Default yoghurt: fat-free (use full-fat only if needed).
- Lunch: Sarah always Greek salad. Louis lunch skipped. Luke Arroz batches (beef/chicken) with explicit leftovers for next-day lunch; note leftovers in the description.
- Dinner: choose weekly variety with 1–2 fish; focus on mince/thighs for budget; Friday can be takeaway. Weeknight prep ≤40 min (Mon 15–20). Keep spice mild; pregnancy-safe; GF-sensitive for Sarah (GF pasta/pizza preferred, avoid bread overload).

4) Calendar event content
- Use the recipe card template (from MEALS.md) in the description:
  - Title
  - Cook time: prep X min + 30 min eating (weeknights ≤40, Mon 15–20)
  - Serves/Spice
  - Ingredients (single list, normalized units)
  - Equipment
  - Mise en place (all prep; note what can share a bowl)
  - Steps (numbered, inline quantities)
  - Notes (GF/pregnancy/spice adjustments, leftovers, use-up flags)

5) Ask when unclear
- If budget/effort/spice/use-up ingredients/outing conflicts are unclear, ask before placing meals.

6) Shopping
- Only generate a shopping list on explicit request. Normalize ingredient names; pack-aware; can push to Google Tasks via `shopping_client.py` when asked.

7) Fish count & protein preference
- Aim for 1–2 fish dinners per week. Default proteins: beef mince, boneless skinless chicken thighs; keep costs low.
