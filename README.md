# NFL MODEL

Weekly NFL fantasy football and betting model for the 2026 season: lineup projections, player-prop expected value, and game-line leans across DraftKings, FanDuel and Fanatics.

The site is a single self-contained `index.html`, served with GitHub Pages. Scheduled updates push a fresh copy here:

- **Tuesday ~9:52 AM ET**: weekly reset for the new slate
- **Daily ~9:55 AM ET (except Tuesday)**: lines, splits, weather, injuries and props
- **Thu/Sun/Mon 12:05, 3:05, 7:05 PM ET**: game-day inactives and final lines

Model outputs only, not betting advice. 21+. Gambling problem? Call 1-800-GAMBLER.

## NFL game lines (`tools/nfl_books.py`)

The NFL Game lines section prices every side at DraftKings, FanDuel, BetMGM and Fanatics, read from the VegasInsider NFL
odds board (https://www.vegasinsider.com/nfl/odds/las-vegas/) in the same raw format as the college board
(`nfl/raw/vi_<date>.txt`, CODE = the page's GAMES key, e.g. `BUF@NYJ`). `python3 tools/nfl_books.py <page.html> <raw file>`
writes each game's per-book spread, total and moneyline quotes into the page's GL block, sets GAMES hs/total to the board's
consensus, and drops quotes far from consensus as stale. Defaults since Nov 17: rating weight 15%, efficiency home field
0.5 pts, fade-the-public and reverse-line-move signals off, moneylines information-only, efficiency weight on totals 40%.
