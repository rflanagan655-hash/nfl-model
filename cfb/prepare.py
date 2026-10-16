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


def num(x):
    return f"{x:g}"


def book_line(g, b):
    """One book's quotes as compact text, e.g. 'Texas -10.5 (-110) · o52.5 -110 / u52.5 -110 · ML +320 / -425'."""
    parts = []
    if b.get("spread_home") is not None:
        s = b["spread_home"]
        fav = (g["home"], s, b["px_spread_home"]) if s <= 0 else (g["away"], -s, b["px_spread_away"])
        dog = (g["away"], -s, b["px_spread_away"]) if s <= 0 else (g["home"], s, b["px_spread_home"])
        parts.append(f"{fav[0]} {line(fav[1])} ({price(fav[2])}) / {dog[0]} {line(dog[1])} ({price(dog[2])})")
    if b.get("total") is not None:
        parts.append(f"O/U {num(b['total'])} ({price(b['px_over'])} / {price(b['px_under'])})")
    if b.get("ml_home") is not None:
        parts.append(f"ML {g['away']} {price(b['ml_away'])} / {g['home']} {price(b['ml_home'])}")
    return " · ".join(parts)


def ats(r):
    return "—" if not r else f"{r[0]}-{r[1]}"


def rk(n):
    return f"#{n}"


def team_line(name, t, avg_x):
    return (f"{name}: SP+ {t['sp']:+.1f} ({rk(t['sp_rk'])}) · offense {t['off']:.1f} ({rk(t['off_rk'])}) · defense {t['def']:.1f} ({rk(t['def_rk'])})")


def to_line(name, t):
    m = t["to_margin"]
    return f"{name}: {t['take_pg']:.1f} takeaways / {t['give_pg']:.1f} giveaways per game (margin {m:+d})"


def y_line(name, t):
    if "ypp_off" not in t:
        return f"{name}: —"
    return (f"{name}: offense {t['ypp_off']:.2f} yds/play ({rk(t['ypp_off_rk'])}), {t['ypg_off']:.0f} yds/g ({rk(t['ypg_off_rk'])}) · "
            f"defense {t['ypp_def']:.2f} yds/play allowed ({rk(t['ypp_def_rk'])}), {t['ypg_def']:.0f} yds/g allowed ({rk(t['ypg_def_rk'])})")


def x_line(name, t):
    return f"{name}: {t['x_off_pg']:.1f} plays of 20+ yds per game, {t['x_def_pg']:.1f} allowed"


rows = []
for g in d["games"]:
    s, ps = g["spread_home"], g["proj_spread_home"]
    sp, tb, ml = g["spread"], g["total_bet"], g["ml"]
    r = g.get("ratings")
    w = g["weather"]
    wx = "Dome" if w["dome"] else f"{w['temp']}°F, {w['wind']} mph" + (f" (gusts {w['gust']})" if w["gust"] else "") + f", {w['rain']}% rain"
    sp_txt = f"{sp['side']} {line(sp['line'])} ({price(sp['price'])}, {sp['book']})"
    tb_txt = f"{tb['side']} {num(tb['line'])} ({price(tb['price'])}, {tb['book']})"
    ml_txt = f"{ml['side']} ML ({price(ml['price'])}, {ml['book']})" if ml else "No moneyline posted"
    cands = [("Spread", sp_txt, sp), ("Total", tb_txt, tb)]
    if ml:
        cands.append(("Moneyline", ml_txt, ml))
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
        "spread_pick": sp_txt, "spread_book": sp["book"],
        "spread_p": sp["p"], "spread_breakeven": sp["breakeven"], "spread_push": sp["push"],
        "spread_ev": sp["ev"], "spread_grade": sp["grade"],
        # total
        "total_pick": tb_txt, "total_book": tb["book"],
        "total_p": tb["p"], "total_breakeven": tb["breakeven"], "total_push": tb["push"],
        "total_ev": tb["ev"], "total_grade": tb["grade"],
        # moneyline
        "ml_pick": ml_txt, "ml_book": ml["book"] if ml else None,
        "ml_p": ml["p"] if ml else None, "ml_breakeven": ml["breakeven"] if ml else None,
        "ml_ev": ml["ev"] if ml else None, "ml_grade": ml["grade"] if ml else "Pass",
        # best bet in the game
        "best_market": best[0], "best_pick": best[1], "best_ev": best[2]["ev"], "best_grade": best[2]["grade"],
        "best_book": best[2]["book"],
        "book_lines": " | ".join(f"{b['book']}: {book_line(g, b)}" for b in g.get("books", [])),
        "books_quoted": len(g.get("books", [])),
        "ratings_line": (("Pick'em" if round(r['margin'], 1) == 0 else f"{g['home']} {line(-round(r['margin'], 1))}" if r['margin'] > 0 else f"{g['away']} {line(round(r['margin'], 1))}") if r else "—"),
        "ratings_total": round(r["total"], 1) if r else None,
        "ratings_score": f"{g['away']} {r['pts_away']:.1f}, {g['home']} {r['pts_home']:.1f}" if r else "—",
        "ratings_teams": (team_line(g['away'], r['away'], 0) + " | " + team_line(g['home'], r['home'], 0)) if r else "—",
        "turnovers": (to_line(g['away'], r['away']) + " | " + to_line(g['home'], r['home'])
                      + f" | Expected giveaways: {g['away']} {r['exp_give_away']:.1f}, {g['home']} {r['exp_give_home']:.1f}") if r else "—",
        "explosives": (x_line(g['away'], r['away']) + " | " + x_line(g['home'], r['home'])
                       + f" | Expected 20+ yd plays: {g['away']} {r['exp_x_away']:.1f}, {g['home']} {r['exp_x_home']:.1f}") if r else "—",
        "yardage": (y_line(g['away'], r['away']) + " | " + y_line(g['home'], r['home'])
                    + (f" | Expected yds/play: {g['away']} {r['exp_ypp_away']:.2f}, {g['home']} {r['exp_ypp_home']:.2f} · expected plays {r['exp_plays']:.0f}" if r.get('exp_ypp_home') else "")) if r else "—",
        "rating_margin_parts": (f"SP+ gap + home field {r['base_margin']:+.1f}, turnovers {r['to_adj']:+.1f}, explosive plays {r['x_adj']:+.1f}, yards per play {r['y_adj']:+.1f} (home view); "
                                f"total: yards per play {r['y_total_adj']:+.1f}, pace {r['pace_total_adj']:+.1f}") if r else "—",
        "ypp_off_rk_away": r["away"].get("ypp_off_rk") if r else None, "ypp_def_rk_away": r["away"].get("ypp_def_rk") if r else None,
        "ypp_off_rk_home": r["home"].get("ypp_off_rk") if r else None, "ypp_def_rk_home": r["home"].get("ypp_def_rk") if r else None,
        "off_rk_away": r["away"]["off_rk"] if r else None, "def_rk_away": r["away"]["def_rk"] if r else None,
        "off_rk_home": r["home"]["off_rk"] if r else None, "def_rk_home": r["home"]["def_rk"] if r else None,
        "sp_rk_away": r["away"]["sp_rk"] if r else None, "sp_rk_home": r["home"]["sp_rk"] if r else None,
        "adj_ratings": g["adj"].get("ratings"), "adj_ratings_total": g["adj"].get("ratings_total"),
        "adj_home_field": g["adj"]["hfa"], "adj_injury": g["adj"]["injury"], "adj_trend": g["adj"]["trend"],
        "adj_weather_total": g["adj"]["weather_total"], "adj_injury_total": g["adj"]["injury_total"],
        "weather": wx, "weather_impact": w["note"],
        "injuries": g["injuries"], "trend_note": g["trend_note"] or "—",
        "ats_away": ats(g["ats_away"]), "ats_home": ats(g["ats_home"]),
        "sources": "; ".join(d["source_index"][k]["title"] for k in g["sources"]),
        "book": d.get("book", "DraftKings"), "prior_book": "DraftKings", "as_of": d["as_of"],
    })
json.dump(rows, open("games_rows.json", "w"), indent=1)
json.dump([{"key": k, "title": v["title"], "url": v["url"]} for k, v in d["source_index"].items()],
          open("sources_rows.json", "w"), indent=1)
n = sum(r[f"{m}_grade"] != "Pass" for r in rows for m in ("spread", "total", "ml"))
print(len(rows), "games;", n, "+EV bets graded Slight or better")
