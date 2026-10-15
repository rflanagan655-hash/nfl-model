"""Merge a VegasInsider board extract into games.json as per-book lines.

Usage: python3 ingest_books.py raw/vi_YYYY-MM-DD.txt games.json [as_of_iso]

Raw format (one line per row, cells after the Open column, in board order):
  CODE row-type: cell | cell | ... (9 cells)
  row-type is spread-away, spread-home, total-over, total-under, ML-away or ML-home.
  Board order: Bet365, BetMGM, DraftKings, Caesars, FanDuel, HardRock, Fanatics, RiversCasino, Consensus.

CODE maps to a game id through CODE_TO_ID (or the game's "vi_code" field in games.json).
DraftKings also refreshes the top-level fields, which stay the model's market prior.
A book quote that strays from consensus (spread or total off by > 3 pts, or moneyline
implied probability off by > 0.12) is treated as stale and dropped.
"""
import json, re, sys

BOARD = ["Bet365", "BetMGM", "DraftKings", "Caesars", "FanDuel", "HardRock", "Fanatics", "RiversCasino", "Consensus"]
BOOKS = ["DraftKings", "FanDuel", "BetMGM", "Fanatics"]
CODE_TO_ID = {
    "ECU@UAB": "ecu-uab", "WAS@PUR": "uw-pur", "WIS@UCLA": "wis-ucla", "CSU@TXST": "csu-txst",
    "GASO@ODU": "gaso-odu", "MEM@TUL": "mem-tul", "APP@CCU": "app-ccu", "OSU@IU": "osu-ind",
    "FLA@TEX": "fla-tex", "MSU@LSU": "msst-lsu", "ALA@TENN": "bama-tenn", "MIZ@MISS": "mizz-miss",
    "AUB@UGA": "aub-uga", "ASU@TTU": "asu-ttu", "PSU@MICH": "psu-mich", "FSU@MIA": "fsu-mia",
    "ND@BYU": "nd-byu", "OKST@HOU": "okst-hou", "KY@OU": "uk-ou", "LOU@SYR": "lou-syr",
    "UTAH@COL": "utah-colo", "FRES@SDSU": "fres-sdsu", "NEB@ORE": "neb-ore",
}


def px(tok):
    tok = tok.strip().lower()
    if tok in ("even", "ev", "+100"):
        return 100
    return int(tok)


def cell(c, kind):
    c = c.strip()
    if not c or c.upper() == "N/A":
        return None
    parts = c.split()
    try:
        if kind == "ml":
            return {"price": px(parts[0])}
        num = parts[0].lstrip("ou")
        if num.upper() == "PK":
            num = "0"
        if num.startswith("--") or num.startswith("+-"):
            return None  # garbled board cell
        return {"line": float(num), "price": px(parts[1])}
    except (ValueError, IndexError):
        return None


def imp(p):
    return 100 / (p + 100) if p > 0 else -p / (-p + 100)


def parse(path):
    rows = {}
    for ln in open(path):
        m = re.match(r"\s*(\S+)\s+(spread-away|spread-home|total-over|total-under|ML-away|ML-home):\s*(.*)", ln)
        if not m:
            continue
        code, rt, rest = m.groups()
        kind = "ml" if rt.startswith("ML") else "line"
        cells = [cell(c, kind) for c in rest.split("|")]
        rows.setdefault(code, {})[rt] = dict(zip(BOARD, cells))
    return rows


def main():
    raw, gpath = sys.argv[1], sys.argv[2]
    data = json.load(open(gpath))
    rows = parse(raw)
    ids = {**CODE_TO_ID, **{g["vi_code"]: g["id"] for g in data["games"] if g.get("vi_code")}}
    by_id = {g["id"]: g for g in data["games"]}
    dropped, filled = [], 0
    for code, r in rows.items():
        g = by_id.get(ids.get(code))
        if not g:
            print("unmatched code", code); continue
        cons = {k: (r.get(k) or {}).get("Consensus") for k in r}
        books = {}
        for b in BOOKS:
            q = {}
            sa, sh = (r.get("spread-away") or {}).get(b), (r.get("spread-home") or {}).get(b)
            ca = cons.get("spread-home")
            if sa and sh and abs(sh["line"] + sa["line"]) < 1e-9 and (not ca or abs(sh["line"] - ca["line"]) <= 3):
                q.update(spread_home=sh["line"], px_spread_home=sh["price"], px_spread_away=sa["price"])
            elif sa or sh:
                dropped.append(f"{code} {b} spread")
            o, u = (r.get("total-over") or {}).get(b), (r.get("total-under") or {}).get(b)
            ct = cons.get("total-over")
            if o and u and o["line"] == u["line"] and (not ct or abs(o["line"] - ct["line"]) <= 3):
                q.update(total=o["line"], px_over=o["price"], px_under=u["price"])
            elif o or u:
                dropped.append(f"{code} {b} total")
            ma, mh = (r.get("ML-away") or {}).get(b), (r.get("ML-home") or {}).get(b)
            cm = cons.get("ML-home")
            if ma and mh and (not cm or abs(imp(mh["price"]) - imp(cm["price"])) <= 0.12):
                q.update(ml_away=ma["price"], ml_home=mh["price"])
            elif ma or mh:
                dropped.append(f"{code} {b} ML")
            if q:
                books[b] = q
        g["books"] = books
        dk = books.get("DraftKings", {})
        for k in ("spread_home", "px_spread_home", "px_spread_away", "total", "px_over", "px_under", "ml_away", "ml_home"):
            if k in dk:
                g[k] = dk[k]
        filled += 1
    data["book"] = "Best of " + ", ".join(BOOKS)
    data["books"] = BOOKS
    if len(sys.argv) > 3:
        data["as_of"] = sys.argv[3]
    json.dump(data, open(gpath, "w"), indent=1)
    print(f"{filled} games updated; dropped as stale/garbled: {', '.join(dropped) or 'none'}")


if __name__ == "__main__":
    main()
