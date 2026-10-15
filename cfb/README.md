# College football model

Weekly DraftKings-priced college football model used by the College football section of NFL MODEL
and by the CFB model dashboard.

- `games.json` — this week's inputs (prices, venue home field, weather, injury adjustments, ATS, sources)
- `model.py` — `python3 model.py games.json model_output.json` (method in its docstring)
- `prepare.py` — `python3 prepare.py model_output.json` writes `games_rows.json` and `sources_rows.json`
- `venues.json` — home-field estimate (`venue_hfa`), dome and altitude flags per home team; reused week to week
- `weeks/` — archived inputs from previous weeks

Updated by scheduled tasks: weekly reset Tuesday ~10:37 AM ET, daily refresh Thu–Sat 9:45 AM ET.

## Multi-book prices (DraftKings, FanDuel, BetMGM, Fanatics)

1. Extract the VegasInsider board into `raw/vi_<date>.txt` (one line per row: `CODE spread-away: cell | cell | ...`,
   nine cells after Open in board order Bet365 | BetMGM | DraftKings | Caesars | FanDuel | HardRock | Fanatics | RiversCasino | Consensus).
2. `python3 ingest_books.py raw/vi_<date>.txt games.json <as_of ISO>` writes each game's `books` quotes and refreshes the
   DraftKings fields (the model's prior). Quotes far from consensus are dropped as stale.
3. `python3 model.py games.json model_output.json && python3 prepare.py model_output.json` prices every side at every
   book on that book's own line; each pick names the book with the best EV, and `book_lines` lists all four books.

## Team ratings, turnovers and explosive plays (`ratings.json`)

Per team: SP+ overall/offense/defense with FBS ranks (cfbupdate.com), turnovers gained/lost (cfbstats.com turnover
margin) and 20+ yard scrimmage plays produced/allowed (cfbstats.com long scrimmage plays, offense and defense).
`model.py` builds a ratings-only projection (SP+ gap + venue HFA; points = offense + opponent defense − 26.3;
turnovers at 4 pts each, 60% regressed; explosive plays at 0.5 pt each) and moves the market-based projection
15% of the way toward it (`RATINGS_WEIGHT`). Refresh `ratings.json` every Tuesday with the same schema.
