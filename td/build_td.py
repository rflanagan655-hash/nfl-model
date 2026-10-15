"""Build the Best Touchdown Bets data block for the NFL MODEL page.

Inputs (this folder): raw_rb.txt, raw_wr.txt, raw_te.txt, raw_qb.txt (FantasyPros 2026 season stats),
team_def_off.txt (SumerSports team offense/defense EPA and TD splits), rz_snap.txt (RosterAudit red-zone
carry/target share and snap %), injuries.txt (status overrides).

Usage: python3 build_td.py <page.html> <as_of_text> <thursday YYYY-MM-DD of the NFL week> [ET offset, default -04:00; use -05:00 after DST ends]
Rewrites the text between /* TD_DATA_START */ and /* TD_DATA_END */ in the page.
"""
import json, re, sys, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {"Buffalo Bills": "BUF", "San Francisco 49ers": "SF", "Detroit Lions": "DET", "Kansas City Chiefs": "KC",
         "Baltimore Ravens": "BAL", "Jacksonville Jaguars": "JAX", "Dallas Cowboys": "DAL", "Carolina Panthers": "CAR",
         "Los Angeles Rams": "LAR", "Cincinnati Bengals": "CIN", "New England Patriots": "NE", "Houston Texans": "HOU",
         "Las Vegas Raiders": "LV", "Chicago Bears": "CHI", "New York Giants": "NYG", "New Orleans Saints": "NO",
         "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "New York Jets": "NYJ", "Green Bay Packers": "GB",
         "Washington Commanders": "WAS", "Indianapolis Colts": "IND", "Pittsburgh Steelers": "PIT", "Denver Broncos": "DEN",
         "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Cleveland Browns": "CLE", "Minnesota Vikings": "MIN",
         "Miami Dolphins": "MIA", "Philadelphia Eagles": "PHI", "Tennessee Titans": "TEN", "Los Angeles Chargers": "LAC"}
FIX = {"JAC": "JAX", "LA": "LAR"}


def team(t):
    t = t.strip().strip("()")
    return FIX.get(t, t)


def norm(n):
    n = re.sub(r"\b(Jr\.?|Sr\.?|II|III|IV)\b", "", n)
    return re.sub(r"[^a-z]", "", n.lower())


def lines(fn):
    for ln in open(os.path.join(HERE, fn), encoding="utf-8"):
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            yield ln


P = {}  # key (norm name, team) -> player


def get(name, tm, pos):
    k = (norm(name), tm)
    if k not in P:
        P[k] = dict(name=name, team=tm, pos=pos, ra=0, rtd=0, tgt=0, rectd=0, g=0, pa=0, ptd=0)
    return P[k]


for ln in lines("raw_rb.txt"):
    n, t, ra, rtd, tg, rec, g = ln.split("|")
    p = get(n, team(t), "RB"); p.update(ra=int(ra), rtd=int(rtd), tgt=int(tg), rectd=int(rec), g=int(g))
for ln in lines("raw_wr.txt"):
    n, t, tg, rc, rectd, ra, rtd, g = ln.split("|")
    p = get(n, team(t), "WR"); p.update(tgt=int(tg), rectd=int(rectd), ra=int(ra), rtd=int(rtd), g=int(g))
for ln in lines("raw_te.txt"):
    n, t, tg, rc, rectd, g = ln.split("|")
    p = get(n, team(t), "TE"); p.update(tgt=int(tg), rectd=int(rectd), g=int(g))
for ln in lines("raw_qb.txt"):
    n, t, pa, ptd, ra, rtd, g = ln.split("|")
    p = get(n, team(t), "QB"); p.update(pa=int(pa), ptd=int(ptd), ra=int(ra), rtd=int(rtd), g=int(g))

OFF, DEF = {}, {}
for ln in lines("team_def_off.txt"):
    kind, rest = ln.split(" ", 1)
    nm, epa, ep, er, ptd, rtd = rest.split("|")
    d = dict(epa=float(epa), pass_epa=float(ep), rush_epa=float(er), ptd=int(ptd), rtd=int(rtd))
    (OFF if kind == "OFF" else DEF)[NAMES[nm]] = d

RZC, RZT, SNAP = {}, {}, {}
for ln in lines("rz_snap.txt"):
    kind, rest = ln.split(" ", 1)
    n, t, v = rest.split("|")
    {"RZC": RZC, "RZT": RZT, "SNAP": SNAP}[kind][(norm(n), team(t))] = float(v)

INJ = {}
if os.path.exists(os.path.join(HERE, "injuries.txt")):
    for ln in lines("injuries.txt"):
        n, t, pa, status = ln.split("|")
        INJ[(norm(n), team(t))] = (float(pa), status.strip())

# team volume per game
tg_games = defaultdict(int)
tra, ttg = defaultdict(float), defaultdict(float)
for p in P.values():
    tg_games[p["team"]] = max(tg_games[p["team"]], p["g"])
for p in P.values():
    tra[p["team"]] += p["ra"]
    ttg[p["team"]] += p["tgt"]


def lookup(D, p):
    k = (norm(p["name"]), p["team"])
    if k in D:
        return D[k]
    # match on last name + team (sources abbreviate first names / suffixes)
    last = norm(p["name"].split()[-1] if not re.match(r"^(Jr|Sr|II|III|IV)\.?$", p["name"].split()[-1]) else p["name"].split()[-2])
    hits = [v for (nn, tt), v in D.items() if tt == p["team"] and nn.endswith(last)]
    return hits[0] if len(hits) == 1 else None


out = []
for p in P.values():
    T = p["team"]
    if not p["g"] or T not in OFF:
        continue
    gT = tg_games[T] or 1
    ge = max(p["g"], min(2, gT))  # a one-game sample counts as two, so a single big game doesn't define a role
    cs = (p["ra"] / ge) / (tra[T] / gT) if tra[T] else 0
    ts = (p["tgt"] / ge) / (ttg[T] / gT) if ttg[T] else 0
    keep = (p["pos"] == "RB" and (cs >= 0.18 or ts >= 0.08)) or (p["pos"] in ("WR", "TE") and ts >= 0.11) \
        or (p["pos"] == "QB" and (p["ra"] / p["g"] >= 3.5 or p["rtd"] >= 2))
    if not keep:
        continue
    pa, status = INJ.get((norm(p["name"]), T), (0.97, "No injury designation"))
    out.append(dict(name=p["name"], team=T, pos=p["pos"], g=p["g"], ra=p["ra"], rtd=p["rtd"], tgt=p["tgt"], rectd=p["rectd"],
                    cs=round(min(cs, 1), 3), ts=round(min(ts, 1), 3),
                    rzc=(lookup(RZC, p) or None) and round(lookup(RZC, p) / 100, 3),
                    rzt=(lookup(RZT, p) or None) and round(lookup(RZT, p) / 100, 3),
                    snap=lookup(SNAP, p), pA=pa, status=status))

data = {"asof": sys.argv[2] if len(sys.argv) > 2 else "",
        "thu": sys.argv[3] if len(sys.argv) > 3 else "", "tz": sys.argv[4] if len(sys.argv) > 4 else "-04:00",
        "teams": {t: {"g": tg_games[t], "rtd": OFF[t]["rtd"], "ptd": OFF[t]["ptd"], "rush_epa": OFF[t]["rush_epa"], "pass_epa": OFF[t]["pass_epa"]} for t in OFF},
        "def": {t: {"rtd": DEF[t]["rtd"], "ptd": DEF[t]["ptd"], "rush_epa": DEF[t]["rush_epa"], "pass_epa": DEF[t]["pass_epa"]} for t in DEF},
        "players": sorted(out, key=lambda x: (x["team"], x["pos"], -x["cs"] - x["ts"]))}

page = sys.argv[1]
s = open(page, encoding="utf-8").read()
blob = "/* TD_DATA_START */const TD_DATA=" + json.dumps(data, separators=(",", ":")).replace("</", "<\\/") + ";/* TD_DATA_END */"
if "/* TD_DATA_START */" in s:
    s = re.sub(r"/\* TD_DATA_START \*/.*?/\* TD_DATA_END \*/", lambda m: blob, s, flags=re.S)
else:
    sys.exit("TD markers not found in page")
open(page, "w", encoding="utf-8").write(s)
print(f"TD block: {len(out)} candidates, {len(data['teams'])} teams")
