"""Flatten model_output.json into the dashboard's row files: games_rows.json, sources_rows.json."""
import json, sys

src = sys.argv[1] if len(sys.argv) > 1 else "model_output.json"
d = json.load(open(src))


def line(x):
    if x is None:
        return "—"
    if x == 0:
        return "PK"
    s = f"{x:+.1f}"
    return s[:-2] if s.endswith(".0") else s


def price(x):
    return "—" if x is None else (f"+{x}" if x > 0 else str(x))


def ats(r):
    return "—" if not r else f"{r[0]}-{r[1]}"


rows = []
for g in d["games"]:
    s, ps = g["spread_home"], g["proj_spread_home"]
    sp, tb, ml = g["spread"], g["total_bet"], g["ml"]
    w = g["weather"]
    wx = "Dome" if w["dome"] else f"{w['temp']}°F, {w['wind']} mph" + (f" (gusts {w['gust']})" if w["gust"] else "") + f", {w['rain']}% rain"
    cands = [("Spread", f"{sp['side']} {line(sp['line'])} ({price(sp['price'])})", sp)]
    cands.append(("Total", f"{tb['side']} {g['total']} ({price(tb['price'])})", tb))
    if ml:
        cands.append(("Moneyline", f"{ml['side']} ML ({price(ml['price'])})", ml))
    best = max(cands, key=lambda c: c[2]["ev"])
    rows.append({
        "id": g["id"], "day": g["day"], "kickoff": g["kickoff"],
        "matchup": f"{g['away']} @ {g['home']}", "away": g["away"], "home": g["home"],
        "market_line": (f"{g['home']} {line(s)}" if s <= 0 else f"{g['away']} {line(-s)}"),
        "spread_home": s, "total": g["total"],
        "spread_prices": f"{g['away']} {price(g['px_spread_away'])} / {g['home']} {price(g['px_spread_home'])}",
        "total_prices": f"Over {price(g['px_over'])} / Under {price(g['px_under'])}",
        "ml_away": price(g["ml_away"]), "ml_home": price(g["ml_home"]),
        "implied_away": g["implied_away"], "implied_home": g["implied_home"],
        "implied_source": "Moneyline, margin removed" if g["implied_source"] == "moneyline" else "Derived from spread",
        "hold": g["hold"],
        "market_score": f"{g['away']} {g['market_score'][0]:.1f}, {g['home']} {g['market_score'][1]:.1f}",
        "model_line": (f"{g['home']} {line(ps)}" if ps <= 0 else f"{g['away']} {line(-ps)}"),
        "proj_spread_home": ps, "proj_total": g["proj_total"],
        "proj_score": f"{g['away']} {g['proj_score'][0]:.1f}, {g['home']} {g['proj_score'][1]:.1f}",
        "model_away": g["model_away"], "model_home": g["model_home"],
        "fair_ml_away": price(g["fair_ml_away"]), "fair_ml_home": price(g["fair_ml_home"]),
        # spread
        "spread_pick": f"{sp['side']} {line(sp['line'])} ({price(sp['price'])})",
        "spread_p": sp["p"], "spread_breakeven": sp["breakeven"], "spread_push": sp["push"],
        "spread_ev": sp["ev"], "spread_grade": sp["grade"],
        # total
        "total_pick": f"{tb['side']} {g['total']} ({price(tb['price'])})",
        "total_p": tb["p"], "total_breakeven": tb["breakeven"], "total_push": tb["push"],
        "total_ev": tb["ev"], "total_grade": tb["grade"],
        # moneyline
        "ml_pick": f"{ml['side']} ML ({price(ml['price'])})" if ml else "No moneyline posted",
        "ml_p": ml["p"] if ml else None, "ml_breakeven": ml["breakeven"] if ml else None,
        "ml_ev": ml["ev"] if ml else None, "ml_grade": ml["grade"] if ml else "Pass",
        # best bet in the game
        "best_market": best[0], "best_pick": best[1], "best_ev": best[2]["ev"], "best_grade": best[2]["grade"],
        "adj_home_field": g["adj"]["hfa"], "adj_injury": g["adj"]["injury"], "adj_trend": g["adj"]["trend"],
        "adj_weather_total": g["adj"]["weather_total"], "adj_injury_total": g["adj"]["injury_total"],
        "weather": wx, "weather_impact": w["note"],
        "injuries": g["injuries"], "trend_note": g["trend_note"] or "—",
        "ats_away": ats(g["ats_away"]), "ats_home": ats(g["ats_home"]),
        "sources": "; ".join(d["source_index"][k]["title"] for k in g["sources"]),
        "book": d.get("book", "DraftKings"), "as_of": d["as_of"],
    })
json.dump(rows, open("games_rows.json", "w"), indent=1)
json.dump([{"key": k, "title": v["title"], "url": v["url"]} for k, v in d["source_index"].items()],
          open("sources_rows.json", "w"), indent=1)
n = sum(r[f"{m}_grade"] != "Pass" for r in rows for m in ("spread", "total", "ml"))
print(len(rows), "games;", n, "+EV bets graded Slight or better")
