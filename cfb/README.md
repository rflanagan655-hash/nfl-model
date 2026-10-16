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

## Yards per play and pace (`ingest_yards.py`)

`raw/tot_off.txt` and `raw/tot_def.txt` hold every FBS team's cfbstats.com Total Offense / Total Defense row
(`Team|G|Plays|Yards|Yards/Play|Yards/G`). `python3 ingest_yards.py raw/tot_off.txt raw/tot_def.txt ratings.json` adds plays and
yards gained/allowed plus national ranks (yards per play and per game) to each slate team, and the FBS average yards per play
and plays per game. In the ratings projection, each side's expected yards per play = its offense + the opponent's defense − FBS
average (each regressed by games/(games+4)); 2.5 pts per 1.0 yd/play of edge on the margin and per yd/play above average on the
total, plus 0.18 pt per expected play above average for pace (all half weight, since SP+ already measures efficiency).

## Restoring inputs from the live page (`sync_from_page.py`)

If a scheduled refresh updated the site but couldn't push, `python3 sync_from_page.py <page.html> games.json` rebuilds the
prices, injuries, weather and ATS inputs from the page's College block so the model reproduces it exactly.

## Moneyline margin removal and the longshot guard

DraftKings' moneylines are turned into fair probabilities with the power method (k such that p_home^k + p_away^k = 1),
not proportional normalising, because books load more margin onto longshots and normalising overstates underdogs.
A moneyline longer than +400 is graded Pass and can't be a game's best bet unless its EV is +10% or more
(`LONGSHOT_PRICE`, `LONGSHOT_EV` in model.py); the tracker applies the same rule.
