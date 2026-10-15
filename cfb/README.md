# College football model

Weekly DraftKings-priced college football model used by the College football section of NFL MODEL
and by the CFB model dashboard.

- `games.json` — this week's inputs (prices, venue home field, weather, injury adjustments, ATS, sources)
- `model.py` — `python3 model.py games.json model_output.json` (method in its docstring)
- `prepare.py` — `python3 prepare.py model_output.json` writes `games_rows.json` and `sources_rows.json`
- `venues.json` — home-field estimate (`venue_hfa`), dome and altitude flags per home team; reused week to week
- `weeks/` — archived inputs from previous weeks

Updated by scheduled tasks: weekly reset Tuesday ~10:37 AM ET, daily refresh Thu–Sat 9:45 AM ET.
