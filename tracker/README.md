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
