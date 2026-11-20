# Model Tracker (game lines)

`ledger.json` mirrors the TRACK block inside the NFL MODEL page (the page copy is the source of truth).
`tools/track.py` maintains it:

    python3 tools/track.py snapshot <page.html>                  # log/refresh pre-kickoff NFL + college lines and leans
    python3 tools/track.py pending <page.html>                   # games that kicked off and need a final score
    python3 tools/track.py result <page.html> <id> <away> <home> # record a final
    python3 tools/track.py summary <page.html>

NFL entries come from the page's own Game lines model (`trackSnapshot()` evaluated in headless Chromium via
tools/page_eval.js); college entries come from the College section's rows. An entry keeps updating until kickoff,
then freezes; the page grades it once a final score is recorded.

# Prop Tracker (kept separate from the game-lines tracker)

`props.json` mirrors the PROPTRACK block inside the page. `tools/prop_track.py` maintains it:

    python3 tools/prop_track.py snapshot <page.html>             # log this week's Top 10 props (EV +$0 to +$3); replaced until the first Sunday kickoff, then locked
    python3 tools/prop_track.py pending <page.html>              # logged props whose game has started and still need the stat
    python3 tools/prop_track.py result <page.html> <id> <stat>   # actual stat (anytime TD: TDs scored; "dnp" = void)
    python3 tools/prop_track.py summary <page.html>

Entries come from the page's `propTrackSnapshot()` (the same `topProps()` list the Top 10 props section shows).
Week 10 was rebuilt after the fact from the Week 10 page with the clock set to Sun Nov 15 12:50 PM ET, and graded
from FantasyData box scores and FFToday game logs.
