"""Week 7 CFB model: implied probability, projections, and expected-value leans.

Method (points from the home team's view; negative spread = home favored):
  1. Market prior: start from DraftKings' posted spread and total (the other books are priced in step 8).
  2. Implied probability: moneylines -> raw probabilities -> bookmaker margin removed by normalising.
     With no moneyline posted, win probability comes from the spread (normal, sd 14).
  3. Home/away: lines assume ~2.5 pts home field. Each venue gets its own estimate; half of
     (venue HFA - 2.5) is applied, since the market already prices some of it.
  4. Injuries: only the part of an absence the line has not already moved for (set in games.json,
     and only from official availability reports or on-record coach/beat-reporter statements).
  5. Trends: season ATS records, shrunk to 0.1 pt per game of net difference, capped at +/-0.75.
  6. Weather (totals): sustained wind >=15 mph -1.5, >=20 -3.0; gusts >=25 another -0.5;
     rain chance >=50% -1.5, >=70% -2.0; kickoff temp <=40F -1.0; altitude +0.5; dome 0.
     Half of that is applied, because public forecasts are already partly in the posted total.
  6b. Team ratings (cfb/ratings.json): SP+ overall, offense and defense; turnovers gained/lost;
     20+ yard plays produced/allowed. A ratings-only projection is built:
        margin = SP+(home) - SP+(away) + venue HFA            (SP+ overall includes special teams)
        points(team) = offense(team) + defense(opponent) - FBS average (26.3)
        total = points(home) + points(away)
        turnovers: expected giveaways(team) = avg(team's giveaways/game, opponent's takeaways/game);
                   margin += 4 pts x 40% x (away expected giveaways - home expected giveaways)
                   (turnover rates are mostly luck, so 60% is regressed away)
        explosive plays: expected 20+ plays(team) = avg(team's 20+ plays/game, opponent's allowed/game);
                   margin += 0.5 pt per extra expected explosive play; total += 0.5 pt per play above average
                   (half weight, since SP+ already measures explosiveness)
     The market stays the anchor: the final projection moves 15% of the way from the market-based
     projection toward the ratings projection (RATINGS_WEIGHT). Ratings don't see this week's injuries.
  7. Probabilities: final margin ~ Normal(projected margin, sd 14); total ~ Normal(projected total, sd 13).
     Whole-number lines get a push probability (the +/-0.5 band around the number).
     Moneyline win probability = vig-free market probability shifted by the model's margin change.
  8. Expected value per $1 risked at the posted price:
        EV = P(win) * profit_per_$1 - P(loss)      (a push returns the stake)
     Every side of every market is priced at every book quoted (DraftKings, FanDuel, BetMGM,
     Fanatics); each book is priced on its own line and price. The best EV across books and
     sides in each market is the candidate, and the book offering it is recorded.
     Grades: EV >= +5% Strong lean, >= +3% Lean, >= +1% Slight, otherwise Pass (no bet).
"""
import json, os, sys
from statistics import NormalDist

SD_MARGIN, SD_TOTAL, BASE_HFA = 14.0, 13.0, 2.5
WEATHER_WEIGHT = 0.5  # forecasts are public, so the posted total already reflects part of them
EV_STRONG, EV_LEAN, EV_SLIGHT = 0.05, 0.03, 0.01
RATINGS_WEIGHT = 0.15          # share of the gap between ratings projection and market projection that is applied
TO_PTS, TO_KEEP = 4.0, 0.40    # points per turnover; share of turnover-rate signal kept after regression
X_PTS = 0.5                    # points per expected 20+ yard play (half weight: SP+ already captures explosiveness)
N = NormalDist()


def american_to_prob(ml):
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def profit_per_dollar(price):
    return price / 100 if price > 0 else 100 / -price


def prob_to_american(p):
    if p <= 0 or p >= 1:
        return None
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def grade(ev):
    return "Strong lean" if ev >= EV_STRONG else "Lean" if ev >= EV_LEAN else "Slight" if ev >= EV_SLIGHT else "Pass"


def over_probs(threshold, mean, sd):
    """P(X > threshold), P(X == threshold) for a line; whole numbers get a push band."""
    if abs(threshold - round(threshold)) < 1e-9:
        p_push = N.cdf((threshold + 0.5 - mean) / sd) - N.cdf((threshold - 0.5 - mean) / sd)
        p_over = 1 - N.cdf((threshold + 0.5 - mean) / sd)
    else:
        p_push = 0.0
        p_over = 1 - N.cdf((threshold - mean) / sd)
    return p_over, p_push


def ev(p_win, p_push, price):
    return p_win * profit_per_dollar(price) - (1 - p_win - p_push)


def weather_adj(g):
    if g.get("dome"):
        return 0.0, "Dome"
    adj, why = 0.0, []
    w, gust, rain, t = g["wind"], g["gust"], g["rain"], g["temp"]
    if w >= 20:
        adj -= 3.0; why.append(f"wind {w} mph")
    elif w >= 15:
        adj -= 1.5; why.append(f"wind {w} mph")
    if gust >= 25:
        adj -= 0.5; why.append(f"gusts {gust}")
    if rain >= 70:
        adj -= 2.0; why.append(f"rain {rain}%")
    elif rain >= 50:
        adj -= 1.5; why.append(f"rain {rain}%")
    if t is not None and t <= 40:
        adj -= 1.0; why.append(f"{t}F")
    if g.get("altitude"):
        adj += 0.5; why.append("altitude")
    return adj, (", ".join(why) if why else "No impact")


def ats_net(rec):
    return 0 if not rec else rec[0] - rec[1]


def team_profile(t):
    return {
        "sp": t["sp"], "sp_rk": t["sp_rk"], "off": t["off"], "off_rk": t["off_rk"], "def": t["def"], "def_rk": t["def_rk"],
        "take_pg": t["takeaways"] / t["to_games"], "give_pg": t["giveaways"] / t["to_games"],
        "to_margin": t["takeaways"] - t["giveaways"],
        "x_off_pg": t["x20_off"] / t["x_games"], "x_def_pg": t["x20_def"] / t["x_games"],
    }


def ratings_projection(home, away, venue_hfa, R):
    """Ratings-only projected home margin and total, with the turnover and explosive-play pieces."""
    T, L = R["teams"], R["league"]["sp_points_avg"]
    if home not in T or away not in T:
        return None
    h, a = team_profile(T[home]), team_profile(T[away])
    x_avg = R["league"].get("x20_avg_pg")
    pts_h = h["off"] + a["def"] - L
    pts_a = a["off"] + h["def"] - L
    base_margin = h["sp"] - a["sp"] + venue_hfa
    give_h = (h["give_pg"] + a["take_pg"]) / 2
    give_a = (a["give_pg"] + h["take_pg"]) / 2
    to_adj = TO_PTS * TO_KEEP * (give_a - give_h)
    xh = (h["x_off_pg"] + a["x_def_pg"]) / 2
    xa = (a["x_off_pg"] + h["x_def_pg"]) / 2
    x_adj = X_PTS * (xh - xa)
    x_tot = X_PTS * ((xh + xa) - 2 * x_avg) if x_avg else 0.0
    return {"home": h, "away": a, "pts_home": pts_h, "pts_away": pts_a,
            "base_margin": base_margin, "to_adj": to_adj, "x_adj": x_adj, "x_total_adj": x_tot,
            "exp_give_home": give_h, "exp_give_away": give_a, "exp_x_home": xh, "exp_x_away": xa,
            "margin": base_margin + to_adj + x_adj, "total": pts_h + pts_a + x_tot}


def run(data, R=None):
    out = []
    for g in data["games"]:
        s, tot = g["spread_home"], g["total"]
        has_ml = g.get("ml_home") is not None and g.get("ml_away") is not None
        if has_ml:
            ph_raw, pa_raw = american_to_prob(g["ml_home"]), american_to_prob(g["ml_away"])
            hold = ph_raw + pa_raw - 1
            mkt_home = ph_raw / (ph_raw + pa_raw)
        else:
            hold = None
            mkt_home = N.cdf(-s / SD_MARGIN)

        hfa_adj = 0.5 * (g["venue_hfa"] - BASE_HFA)
        inj_adj = g["inj_adj_home"]
        trend_adj = max(-0.75, min(0.75, 0.1 * (ats_net(g.get("ats_home")) - ats_net(g.get("ats_away")))))
        w_adj, w_note = weather_adj(g)
        rp = ratings_projection(g["home"], g["away"], g["venue_hfa"], R) if R else None
        mkt_based_margin = -s + hfa_adj + inj_adj + trend_adj
        mkt_based_total = tot + WEATHER_WEIGHT * w_adj + g["inj_total_adj"]
        r_margin_adj = RATINGS_WEIGHT * (rp["margin"] - (-s + hfa_adj)) if rp else 0.0
        r_total_adj = RATINGS_WEIGHT * (rp["total"] - tot) if rp else 0.0
        proj_margin = mkt_based_margin + r_margin_adj
        proj_spread = -proj_margin
        proj_total = mkt_based_total + r_total_adj

        delta = proj_margin - (-s)
        model_home = N.cdf((N.inv_cdf(min(max(mkt_home, 1e-6), 1 - 1e-6)) * SD_MARGIN + delta) / SD_MARGIN)

        quotes = g.get("books") or {}
        if not quotes:
            quotes = {data.get("book", "DraftKings"): {k: g.get(k) for k in (
                "spread_home", "px_spread_home", "px_spread_away", "total", "px_over", "px_under", "ml_home", "ml_away")}}
        sp_c, tt_c, ml_c, book_rows = [], [], [], []
        for b, q in quotes.items():
            row = {"book": b}
            if q.get("spread_home") is not None:
                bs = q["spread_home"]
                p_h, p_ps = over_probs(-bs, proj_margin, SD_MARGIN)
                p_a = 1 - p_h - p_ps
                eh, ea = ev(p_h, p_ps, q["px_spread_home"]), ev(p_a, p_ps, q["px_spread_away"])
                sp_c.append(dict(side=g["home"], line=bs, price=q["px_spread_home"], p=p_h, ev=eh, push=p_ps, book=b))
                sp_c.append(dict(side=g["away"], line=-bs, price=q["px_spread_away"], p=p_a, ev=ea, push=p_ps, book=b))
                row.update(spread_home=bs, px_spread_home=q["px_spread_home"], px_spread_away=q["px_spread_away"],
                           ev_spread_home=eh, ev_spread_away=ea)
            if q.get("total") is not None:
                bt = q["total"]
                p_o, p_pt = over_probs(bt, proj_total, SD_TOTAL)
                p_u = 1 - p_o - p_pt
                eo, eu = ev(p_o, p_pt, q["px_over"]), ev(p_u, p_pt, q["px_under"])
                tt_c.append(dict(side="Over", line=bt, price=q["px_over"], p=p_o, ev=eo, push=p_pt, book=b))
                tt_c.append(dict(side="Under", line=bt, price=q["px_under"], p=p_u, ev=eu, push=p_pt, book=b))
                row.update(total=bt, px_over=q["px_over"], px_under=q["px_under"], ev_over=eo, ev_under=eu)
            if has_ml and q.get("ml_home") is not None and q.get("ml_away") is not None:
                emh, ema = ev(model_home, 0, q["ml_home"]), ev(1 - model_home, 0, q["ml_away"])
                ml_c.append(dict(side=g["home"], price=q["ml_home"], p=model_home, ev=emh, book=b))
                ml_c.append(dict(side=g["away"], price=q["ml_away"], p=1 - model_home, ev=ema, book=b))
                row.update(ml_home=q["ml_home"], ml_away=q["ml_away"], ev_ml_home=emh, ev_ml_away=ema)
            book_rows.append(row)
        # ties go to the earlier book in the list (DraftKings first)
        best = lambda c: max(c, key=lambda x: x["ev"]) if c else None
        sp, tt, ml = best(sp_c), best(tt_c), best(ml_c)
        ev_home = max((c["ev"] for c in sp_c if c["side"] == g["home"]), default=None)
        ev_away = max((c["ev"] for c in sp_c if c["side"] == g["away"]), default=None)
        ev_over = max((c["ev"] for c in tt_c if c["side"] == "Over"), default=None)
        ev_under = max((c["ev"] for c in tt_c if c["side"] == "Under"), default=None)
        for x in (sp, tt, ml):
            if x:
                x["breakeven"] = american_to_prob(x["price"])
                x.pop("push", None) if x is ml else None
        if not has_ml:
            ml = None

        r4 = lambda x: None if x is None else round(x, 4)
        out.append({
            **{k: g[k] for k in ("id", "day", "kickoff", "away", "home")},
            "spread_home": s, "total": tot,
            "px_spread_home": g["px_spread_home"], "px_spread_away": g["px_spread_away"],
            "px_over": g["px_over"], "px_under": g["px_under"],
            "ml_away": g.get("ml_away"), "ml_home": g.get("ml_home"),
            "implied_home": r4(mkt_home), "implied_away": r4(1 - mkt_home),
            "implied_source": "moneyline" if has_ml else "spread", "hold": r4(hold),
            "market_score": [round(tot / 2 + s / 2, 1), round(tot / 2 - s / 2, 1)],
            "adj": {"hfa": round(hfa_adj, 2), "injury": inj_adj, "trend": round(trend_adj, 2),
                     "ratings": round(r_margin_adj, 2), "ratings_total": round(r_total_adj, 2),
                     "weather_total": round(WEATHER_WEIGHT * w_adj, 2), "injury_total": g["inj_total_adj"]},
            "ratings": None if not rp else {
                "home": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in rp["home"].items()},
                "away": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in rp["away"].items()},
                **{k: round(rp[k], 2) for k in ("pts_home", "pts_away", "base_margin", "to_adj", "x_adj", "x_total_adj",
                                                "exp_give_home", "exp_give_away", "exp_x_home", "exp_x_away", "margin", "total")}},
            "weather": {"temp": g["temp"], "wind": g["wind"], "gust": g["gust"], "rain": g["rain"],
                         "dome": g["dome"], "altitude": g["altitude"], "note": w_note},
            "proj_spread_home": round(proj_spread, 1), "proj_total": round(proj_total, 1),
            "proj_score": [round(proj_total / 2 - proj_margin / 2, 1), round(proj_total / 2 + proj_margin / 2, 1)],
            "model_home": r4(model_home), "model_away": r4(1 - model_home),
            "fair_ml_home": prob_to_american(model_home), "fair_ml_away": prob_to_american(1 - model_home),
            "spread": {**{k: (r4(v) if isinstance(v, float) else v) for k, v in sp.items()}, "grade": grade(sp["ev"]),
                        "ev_home": r4(ev_home), "ev_away": r4(ev_away)},
            "total_bet": {**{k: (r4(v) if isinstance(v, float) else v) for k, v in tt.items()}, "grade": grade(tt["ev"]),
                           "ev_over": r4(ev_over), "ev_under": r4(ev_under)},
            "ml": None if ml is None else {**{k: (r4(v) if isinstance(v, float) else v) for k, v in ml.items()}, "grade": grade(ml["ev"])},
            "books": [{k: (r4(v) if isinstance(v, float) and k.startswith("ev") else v) for k, v in br.items()} for br in book_rows],
            "injuries": g["injuries"], "trend_note": g["trend_note"],
            "ats_away": g.get("ats_away"), "ats_home": g.get("ats_home"), "sources": g["sources"],
        })
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "games.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "model_output.json"
    data = json.load(open(src))
    rpath = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(src)), "ratings.json")
    R = json.load(open(rpath)) if os.path.exists(rpath) else None
    if R and "x20_avg_pg" not in R["league"]:
        ts = R["teams"].values()
        R["league"]["x20_avg_pg"] = sum((t["x20_off"] + t["x20_def"]) / 2 / t["x_games"] for t in ts) / len(ts)
    res = run(data, R)
    json.dump({"as_of": data["as_of"], "book": data.get("book", "DraftKings"), "books": data.get("books", [data.get("book", "DraftKings")]), "games": res,
               "source_index": {**data["source_index"], **({"r_" + k: v for k, v in R["sources"].items()} if R else {})},
               "ratings_as_of": R["as_of"] if R else None}, open(dst, "w"), indent=1)
    for r in res:
        sp, t, m = r["spread"], r["total_bet"], r["ml"]
        print(f"{r['away'][:14]:>14} @ {r['home'][:14]:<14} | {sp['side'][:12]} {sp['line']:+} {sp['price']} {sp['book'][:4]} EV {sp['ev']:+.1%} {sp['grade']:<11}"
              f"| {t['side']} {t['line']} {t['price']} {t['book'][:4]} EV {t['ev']:+.1%} {t['grade']:<11}"
              + (f"| ML {m['side'][:12]} {m['price']} {m['book'][:4]} EV {m['ev']:+.1%} {m['grade']}" if m else "| ML n/a"))
