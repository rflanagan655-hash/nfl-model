"""Load NFL game lines from a VegasInsider odds-board extract into the NFL MODEL page (same raw format as cfb/raw/vi_*.txt).

Usage: python3 tools/nfl_books.py <page.html> <raw file>

Raw format (one line per row, the 9 cells after the Open cell, in board order):
  CODE row-type: cell | cell | ...
  CODE is the page's GAMES key (AWAY@HOME, e.g. "BUF@NYJ"); row-type is spread-away, spread-home, total-over,
  total-under, ML-away or ML-home. Board order: Bet365, BetMGM, DraftKings, Caesars, FanDuel, HardRock, Fanatics,
  RiversCasino (the board may show Kalshi in this slot; unused), Consensus.

For every game in the raw file it writes GL[game].dk / .fd / .mgm / .fan = {hs, hp, ap, t, op, up, hm, am}
(home spread and prices, total and over/under prices, moneylines; fields a book didn't post are omitted) and sets
GAMES[game].hs and .total to the board's Consensus spread and total. GL[game].fpi is kept. A book quote that strays
from consensus (spread > 1.5 pts, total > 2 pts, moneyline implied probability > 0.08) is dropped as stale.
Games not in the raw file are left unchanged.
"""
import json, re, subprocess, sys

BOARD = ["Bet365", "BetMGM", "DraftKings", "Caesars", "FanDuel", "HardRock", "Fanatics", "RiversCasino", "Consensus"]
BOOKS = {"DraftKings": "dk", "FanDuel": "fd", "BetMGM": "mgm", "Fanatics": "fan"}
SPREAD_STALE, TOTAL_STALE, ML_STALE = 1.5, 2.0, 0.08


def px(tok):
    tok = tok.strip().lower()
    return 100 if tok in ("even", "ev") else int(tok)


def cell(c, kind):
    c = c.strip()
    if not c or c.upper() == "N/A":
        return None
    parts = c.split()
    try:
        if kind == "ml":
            return {"price": px(parts[0])}
        num = parts[0].lstrip("ou")
        num = "0" if num.upper() in ("PK", "+0", "-0") else num
        return {"line": float(num), "price": px(parts[1])}
    except (ValueError, IndexError):
        return None


def imp(p):
    return 100 / (p + 100) if p > 0 else -p / (-p + 100)


def parse(path):
    rows = {}
    for ln in open(path, encoding="utf-8"):
        m = re.match(r"\s*(\S+)\s+(spread-away|spread-home|total-over|total-under|ML-away|ML-home):\s*(.*)", ln)
        if not m:
            continue
        code, rt, rest = m.groups()
        cells = [cell(c, "ml" if rt.startswith("ML") else "line") for c in rest.split("|")]
        if len(cells) != 9:
            print(f"skipped {code} {rt}: {len(cells)} cells, need 9")
            continue
        rows.setdefault(code, {})[rt] = dict(zip(BOARD, cells))
    return rows


def js_obj(src):
    out = subprocess.run(["node", "-e", "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>process.stdout.write(JSON.stringify(eval('('+s+')'))))"],
                         input=src, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    page, raw = sys.argv[1], sys.argv[2]
    s = open(page, encoding="utf-8").read()
    m = re.search(r"const GL=(\{.*?\n\});", s, re.S)
    if not m:
        sys.exit("GL block not found")
    GL = js_obj(m.group(1))
    rows = parse(raw)
    done, dropped = [], []
    for code, r in rows.items():
        if code not in GL:
            print("not in GL (check the code matches a GAMES key):", code)
            continue
        get = lambda rt, b: (r.get(rt) or {}).get(b)
        csh, ct = get("spread-home", "Consensus"), get("total-over", "Consensus")
        cmh = get("ML-home", "Consensus")
        cons_hs = csh["line"] if csh else None
        cons_t = ct["line"] if ct else None
        for bname, key in BOOKS.items():
            q = {}
            sa, sh = get("spread-away", bname), get("spread-home", bname)
            if sa and sh and abs(sa["line"] + sh["line"]) < 1e-9:
                if cons_hs is None or abs(sh["line"] - cons_hs) <= SPREAD_STALE:
                    q.update(hs=sh["line"], hp=sh["price"], ap=sa["price"])
                else:
                    dropped.append(f"{code} {bname} spread")
            o, u = get("total-over", bname), get("total-under", bname)
            if o and u and o["line"] == u["line"]:
                if cons_t is None or abs(o["line"] - cons_t) <= TOTAL_STALE:
                    q.update(t=o["line"], op=o["price"], up=u["price"])
                else:
                    dropped.append(f"{code} {bname} total")
            ma, mh = get("ML-away", bname), get("ML-home", bname)
            if ma and mh:
                if cmh is None or abs(imp(mh["price"]) - imp(cmh["price"])) <= ML_STALE:
                    q.update(hm=mh["price"], am=ma["price"])
                else:
                    dropped.append(f"{code} {bname} ML")
            if q:
                GL[code][key] = q
            else:
                GL[code].pop(key, None)
        # consensus spread / total -> GAMES
        gb = re.search(r"const GAMES=\{.*?\n\};", s, re.S)
        gm = re.search(r'("' + re.escape(code) + r'":\{[^}]*\})', gb.group(0)) if gb else None
        if gm:
            line = gm.group(1)
            if cons_hs is not None:
                line = re.sub(r"hs:-?[\d.]+", f"hs:{cons_hs:g}", line, count=1)
            if cons_t is not None:
                line = re.sub(r"total:[\d.]+", f"total:{cons_t:g}", line, count=1)
            s = s[:gb.start()] + gb.group(0).replace(gm.group(1), line, 1) + s[gb.end():]
        done.append(code)
    m = re.search(r"const GL=(\{.*?\n\});", s, re.S)
    blob = "{\n" + ",\n".join(f" {json.dumps(k)}:{json.dumps(v, separators=(',', ':'))}" for k, v in GL.items()) + "\n}"
    s = s[:m.start(1)] + blob + s[m.end(1):]
    open(page, "w", encoding="utf-8").write(s)
    print(f"{len(done)} games updated; dropped as stale: {', '.join(dropped) or 'none'}")


if __name__ == "__main__":
    main()
