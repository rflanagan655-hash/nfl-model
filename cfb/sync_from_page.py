"""Rebuild games.json inputs from the CFB block of a published NFL MODEL page.

Use when a scheduled refresh updated the live page but its games.json never reached the repo.
Usage: python3 sync_from_page.py <page.html> games.json
Restores from each row: every book's quotes (book_lines), DraftKings top-level prior, injury adjustments and text,
weather (temp, wind, gusts, rain), ATS records, trend note and as_of. Venue, dome and altitude stay as in games.json.
"""
import json, re, sys

page, gpath = sys.argv[1], sys.argv[2]
s = open(page, encoding="utf-8").read()
cfb = json.loads(re.search(r"/\* CFB_DATA_START \*/const CFB=(.*?);/\* CFB_DATA_END \*/", s, re.S).group(1).replace("<\\/", "</"))
data = json.load(open(gpath))
by = {g["id"]: g for g in data["games"]}


def num(t):
    return 0.0 if t == "PK" else float(t)


def px(t):
    return int(t)


def parse_book(txt, away, home):
    q = {}
    for part in txt.split(" · "):
        if part.startswith("O/U "):
            m = re.match(r"O/U ([\d.]+) \(([+-]\d+) / ([+-]\d+)\)", part)
            q.update(total=float(m[1]), px_over=px(m[2]), px_under=px(m[3]))
        elif part.startswith("ML "):
            m = re.match(rf"ML {re.escape(away)} ([+-]\d+) / {re.escape(home)} ([+-]\d+)", part)
            q.update(ml_away=px(m[1]), ml_home=px(m[2]))
        else:
            m = re.match(r"(.+) (PK|[+-][\d.]+) \(([+-]\d+)\) / (.+) (PK|[+-][\d.]+) \(([+-]\d+)\)", part)
            t1, l1, p1, t2, l2, p2 = m.groups()
            side = {t1: (num(l1), px(p1)), t2: (num(l2), px(p2))}
            q.update(spread_home=side[home][0], px_spread_home=side[home][1], px_spread_away=side[away][1])
    return q


def ats(t):
    return None if not t or t == "—" else [int(x) for x in t.split("-")]


n = 0
for r in cfb["rows"]:
    g = by.get(r["id"])
    if not g:
        print("not in games.json:", r["id"]); continue
    books = {}
    for chunk in (r.get("book_lines") or "").split(" | "):
        if ": " in chunk:
            b, txt = chunk.split(": ", 1)
            books[b] = parse_book(txt, r["away"], r["home"])
    if books:
        g["books"] = books
        for k, v in books.get("DraftKings", {}).items():
            g[k] = v
    g["inj_adj_home"] = r.get("adj_injury") or 0
    g["inj_total_adj"] = r.get("adj_injury_total") or 0
    g["injuries"] = r.get("injuries") or g.get("injuries")
    w = r.get("weather") or ""
    m = re.match(r"(-?\d+)°F, (\d+) mph(?: \(gusts (\d+)\))?, (\d+)% rain", w)
    if m:
        g.update(temp=int(m[1]), wind=int(m[2]), gust=int(m[3] or 0), rain=int(m[4]))
    g["ats_away"], g["ats_home"] = ats(r.get("ats_away")), ats(r.get("ats_home"))
    g["trend_note"] = "" if r.get("trend_note") in (None, "—") else r["trend_note"]
    n += 1
data["as_of"] = cfb.get("updated") or data["as_of"]
json.dump(data, open(gpath, "w"), indent=1)
print(f"{n} games restored from page (as of {data['as_of']})")
