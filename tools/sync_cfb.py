"""Replace the college football data block in the NFL MODEL page.

Usage: python3 tools/sync_cfb.py <page.html> <games_rows.json> <sources_rows.json> [week] [dates]
Rewrites the text between /* CFB_DATA_START */ and /* CFB_DATA_END */ in place.
"""
import json, re, sys

page, games_f, sources_f = sys.argv[1:4]
s = open(page, encoding="utf-8").read()
m = re.search(r"/\* CFB_DATA_START \*/const CFB=(.*?);/\* CFB_DATA_END \*/", s, re.S)
if not m:
    sys.exit("CFB data markers not found in page")
old = json.loads(m.group(1).replace("<\\/", "</"))

rows = json.load(open(games_f, encoding="utf-8"))
if isinstance(rows, dict):
    rows = rows.get("rows") or rows.get("data") or rows.get("results")
sources = json.load(open(sources_f, encoding="utf-8"))
keep = ["id","day","kickoff","matchup","away","home","market_line","total","spread_prices","total_prices","ml_away","ml_home",
        "implied_away","implied_home","model_line","proj_total","proj_score","model_away","model_home","fair_ml_away","fair_ml_home",
        "spread_pick","spread_p","spread_breakeven","spread_push","spread_ev","spread_grade","total_pick","total_p","total_breakeven",
        "total_push","total_ev","total_grade","ml_pick","ml_p","ml_breakeven","ml_ev","ml_grade","best_pick","best_ev","best_grade",
        "adj_home_field","adj_injury","adj_trend","adj_weather_total","adj_injury_total","weather","weather_impact","injuries",
        "trend_note","ats_away","ats_home","as_of","spread_book","total_book","ml_book","best_book","book_lines","books_quoted","ratings_line","ratings_total","ratings_score","ratings_teams","turnovers","explosives",
        "rating_margin_parts","adj_ratings","adj_ratings_total","sp_rk_away","sp_rk_home","off_rk_away","def_rk_away","off_rk_home","def_rk_home"]
cfb = {
    "week": int(sys.argv[4]) if len(sys.argv) > 4 else old.get("week"),
    "dates": sys.argv[5] if len(sys.argv) > 5 else old.get("dates"),
    "updated": max((r.get("as_of") or "") for r in rows) or old.get("updated"),
    "book": next((r.get("book") for r in rows if r.get("book")), old.get("book", "DraftKings")),
    "dashboard": old.get("dashboard"),
    "rows": [{k: r.get(k) for k in keep} for r in rows],
    "sources": sources,
}
blob = json.dumps(cfb, separators=(",", ":")).replace("</", "<\\/")
s = s[:m.start()] + "/* CFB_DATA_START */const CFB=" + blob + ";/* CFB_DATA_END */" + s[m.end():]
open(page, "w", encoding="utf-8").write(s)
print(f"CFB block updated: week {cfb['week']}, {len(cfb['rows'])} games, as of {cfb['updated']}")
