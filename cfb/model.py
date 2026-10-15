"""Week 7 CFB model: implied probability, projections, and expected-value leans.

Method (points from the home team's view; negative spread = home favored):
  1. Market prior: start from DraftKings' posted spread and total.
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
  7. Probabilities: final margin ~ Normal(projected margin, sd 14); total ~ Normal(projected total, sd 13).
     Whole-number lines get a push probability (the +/-0.5 band around the number).
     Moneyline win probability = vig-free market probability shifted by the model's margin change.
  8. Expected value per $1 risked at the posted price:
        EV = P(win) * profit_per_$1 - P(loss)      (a push returns the stake)
     Every side of every market is priced; the better side in each market is the candidate.
     Grades: EV >= +5% Strong lean, >= +3% Lean, >= +1% Slight, otherwise Pass (no bet).
"""
import json, sys
from statistics import NormalDist

SD_MARGIN, SD_TOTAL, BASE_HFA = 14.0, 13.0, 2.5
WEATHER_WEIGHT = 0.5  # forecasts are public, so the posted total already reflects part of them
EV_STRONG, EV_LEAN, EV_SLIGHT = 0.05, 0.03, 0.01
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


def run(data):
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
        proj_spread = s - hfa_adj - inj_adj - trend_adj
        proj_margin = -proj_spread
        w_adj, w_note = weather_adj(g)
        proj_total = tot + WEATHER_WEIGHT * w_adj + g["inj_total_adj"]

        delta = proj_margin - (-s)
        model_home = N.cdf((N.inv_cdf(min(max(mkt_home, 1e-6), 1 - 1e-6)) * SD_MARGIN + delta) / SD_MARGIN)

        # ---- spread: home covers when margin > -s
        p_home, p_push_s = over_probs(-s, proj_margin, SD_MARGIN)
        p_away = 1 - p_home - p_push_s
        ev_home = ev(p_home, p_push_s, g["px_spread_home"])
        ev_away = ev(p_away, p_push_s, g["px_spread_away"])
        if ev_home >= ev_away:
            sp = dict(side=g["home"], line=s, price=g["px_spread_home"], p=p_home, ev=ev_home)
        else:
            sp = dict(side=g["away"], line=-s, price=g["px_spread_away"], p=p_away, ev=ev_away)
        sp["push"] = p_push_s
        sp["breakeven"] = american_to_prob(sp["price"])

        # ---- total
        p_over, p_push_t = over_probs(tot, proj_total, SD_TOTAL)
        p_under = 1 - p_over - p_push_t
        ev_over = ev(p_over, p_push_t, g["px_over"])
        ev_under = ev(p_under, p_push_t, g["px_under"])
        if ev_over >= ev_under:
            tt = dict(side="Over", price=g["px_over"], p=p_over, ev=ev_over)
        else:
            tt = dict(side="Under", price=g["px_under"], p=p_under, ev=ev_under)
        tt["push"] = p_push_t
        tt["breakeven"] = american_to_prob(tt["price"])

        # ---- moneyline
        if has_ml:
            ev_ml_home = ev(model_home, 0, g["ml_home"])
            ev_ml_away = ev(1 - model_home, 0, g["ml_away"])
            if ev_ml_home >= ev_ml_away:
                ml = dict(side=g["home"], price=g["ml_home"], p=model_home, ev=ev_ml_home)
            else:
                ml = dict(side=g["away"], price=g["ml_away"], p=1 - model_home, ev=ev_ml_away)
            ml["breakeven"] = american_to_prob(ml["price"])
        else:
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
                     "weather_total": round(WEATHER_WEIGHT * w_adj, 2), "injury_total": g["inj_total_adj"]},
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
            "injuries": g["injuries"], "trend_note": g["trend_note"],
            "ats_away": g.get("ats_away"), "ats_home": g.get("ats_home"), "sources": g["sources"],
        })
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "games.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "model_output.json"
    data = json.load(open(src))
    res = run(data)
    json.dump({"as_of": data["as_of"], "book": data.get("book", "DraftKings"), "games": res,
               "source_index": data["source_index"]}, open(dst, "w"), indent=1)
    for r in res:
        sp, t, m = r["spread"], r["total_bet"], r["ml"]
        print(f"{r['away'][:16]:>16} @ {r['home'][:16]:<16} | {sp['side'][:12]} {sp['line']:+} {sp['price']} p={sp['p']:.3f} EV {sp['ev']:+.1%} {sp['grade']:<11}"
              f"| {t['side']} {r['total']} {t['price']} p={t['p']:.3f} EV {t['ev']:+.1%} {t['grade']:<11}"
              + (f"| ML {m['side'][:12]} {m['price']} EV {m['ev']:+.1%} {m['grade']}" if m else "| ML n/a"))
