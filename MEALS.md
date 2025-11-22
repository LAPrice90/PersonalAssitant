# Meal Planning & Chef Profile

## People
- Luke: high-protein, budget-aware; lunch often Arroz batches; eats all meals.
- Sarah: lighter calories, pregnancy-safe, gluten-free pasta when applicable; lunch always Greek salad.
- Louis: breakfast/dinner only; mild spice; lunch not needed (school/nursery/work).

## Goals & Constraints
- Variety and nutrition, low/medium cost; include fish 1–2x/week.
- Pregnancy-safe; limit gluten for Sarah (GF pasta/pizza preferred but occasional regular OK; avoid bread overload), mild spice for Louis.
- Cooking time: keep weeknight meals ≤40 minutes prep (Monday 15–20). Display time as “prep X min + 30 min eating” so total window is clear. If longer is needed, only by explicit request.
- Pack efficiency: use full packs where possible; avoid orphan amounts; normalize ingredient names to prevent duplicates in the shopping list.
- Units: solids in grams; liquids in ml; discrete items stay as counts; tsp/tbsp include weight in parentheses (e.g., 1 tsp (5g)).

## Meal Patterns (flexible)
- Breakfast: favorites include poached eggs on toast; scrambled eggs (with/without toast); Greek yoghurt + fruit; French toast + fruit + Greek yoghurt; Turkish eggs. Fruits you stock: raspberries, blueberries, bananas. Default yoghurt: fat-free; if a dinner needs full-fat, note it. Rotate; try not to repeat any one breakfast more than twice per week. Sunday brunch can be larger (eggs/bacon/avocado/potato), but optional.
  - Sarah: if breakfast is Turkish eggs, swap hers to yoghurt + fruit or poached eggs on toast.
  - Lunch: Sarah = Greek salad fixed. Louis = skip. Luke = Arroz batches (beef/chicken as desired) or cheaper protein; batch with explicit portions (same day + next day).
  - Dinner: flexible mix; include 1–2 fish dinners weekly; mix chicken/beef/veg as suits budget/variety. Friday no-cook/cheap option if desired.
  - Snacks (optional, Sarah): yoghurt + honey; bananas; oranges; hummus + carrots; crackers + cheddar; nuts; PB toast; avocado; fruit.

## Recipes (format & behavior)
- Never assume cuisine picker; ask brief clarifications if needed (budget/effort/spice/people). Ask about use-up ingredients when available.
- Recipe card template (use for every meal and in calendar descriptions):
  - Title
  - Cook time: prep X min + 30 min eating (weeknights ≤40 min, Mon 15–20 min)
  - Serves / Spice: who it feeds; spice level (mild by default)
  - Ingredients: single list, normalized names/units (g/ml/each; tsp/tbsp with g)
  - Equipment: matched to inventory
  - Mise en place: all prep here (chop/size, mince/press, what can share a bowl because they cook together)
  - Steps: numbered, with inline ingredient quantities per step
  - Notes: GF/pregnancy/spice adjustments, leftovers (e.g., Arroz next-day lunch), use-up flags
  - Equipment inventory: sauté pan w/ lid, cast iron pans 10/8/6in, Le Creuset saucepans 16/18/20cm w/ lids, 6L Dutch oven, carbon steel wok, small coated saucepan, oven/hob, microwave 900W, sous vide (occasional), mandolin, blender, mortar/pestle, pasta roller, teppanyaki/griddle, burger press, basic utensils/boards.
  - Spice rack: assume common pantry spices are available (e.g., paprika, cumin, coriander, chili powder/flakes, oregano, thyme, rosemary, curry powder/garam masala, garlic/onion powder, black pepper). Use them for flavor; note spice level and keep mild for Louis.
  - Midweek: simple/quick/minimal cleanup. Weekend: can be elaborate if requested.
  - Audience tuning: adjust spice/portions/macros for Luke/Sarah/Louis; mark GF pasta for Sarah; keep pregnancy-safe.
- Pack efficiency: plan recipes/shopping to use full packs across the week; avoid duplicate ingredient names.
- When scheduling meals, include the full recipe card in the calendar description (title, cook time, ingredients, equipment, mise en place, steps, macros if known).

## Planning JSON (baseline fields)
- `week`: ISO week or date range
- `days`: array of objects:
  - `date`
  - `meals`: breakfast/lunch/dinner entries with `people`, `recipe_ref`, `portions`, `cook_time`
- `ingredients`: normalized list with `name`, `qty`, `unit`, optional `notes`
- `shopping`: pack-aware list with `name`, `pack_size`, `packs_needed`, `unit`, `notes`
- `notes`: GF/pregnancy/fish count, budget notes

## Baseline defaults (can be adjusted weekly)
- Fish: target 1–2 dinners/week.
- Monday dinner: keep cook time ~15–20 min; always show cook time.
- Lunches: Sarah Greek salad; Luke Arroz batches; Louis lunch skipped.
- Dinners: pick per-week variety; Friday can be no-cook/cheap if desired.
- Ask questions before locking menus if constraints unclear (effort, budget, spice, any exceptions).
