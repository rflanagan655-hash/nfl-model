"""Model Tracker: log each game's model line/lean before kickoff and grade it after the final.

The ledger lives in the page itself, between /* TRACK_DATA_START */ and /* TRACK_DATA_END */, and is mirrored
to tracker/ledger.json in this repo. Every command edits <page.html> in place.

  python3 tools/track.py snapshot <page.html>           log NFL games (from the page's Game lines model) and college
                                                         games (from the page's College section) that haven't kicked off;
                                                         an entry is overwritten until kickoff, then frozen
  python3 tools/track.py snapshot <page.html> --include-started   same, but also logs started games that have no entry yet
  python3 tools/track.py pending <page.html>            list logged games that have kicked off and still need a final score
  python3 tools/track.py result <page.html> <id> <away_pts> <home_pts>   record a final score
  python3 tools/track.py summary <page.html>            print the season record
"""
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = re.compile(r"/\* TRACK_DATA_START \*/const TRACK=(.*?);/\* TRACK_DATA_END \*/", re.S)
ET = timezone(timedelta(hours=-4))  # EDT; switch to -5 after Nov 1 is handled by start times written from the page


def load(page):
    s = open(page, encoding="utf-8").read()
    m = MARK.search(s)
    if not m:
        sys.exit("TRACK markers not found")
    return s, json.loads(m.group(1).replace("<\\/", "</"))


def save(page, s, T):
    T["updated"] = datetime.now(ET).strftime("%a %b %d, %Y %I:%M %p ET").replace(" 0", " ")
    blob = "/* TRACK_DATA_START */const TRACK=" + json.dumps(T, separators=(",", ":")).replace("</", "<\\/") + ";/* TRACK_DATA_END */"
    s = MARK.sub(lambda m: blob, s)
    open(page, "w", encoding="utf-8").write(s)
    os.makedirs(os.path.join(ROOT, "tracker"), exist_ok=True)
    json.dump(T, open(os.path.join(ROOT, "tracker", "ledger.json"), "w"), indent=1)


def now():
    return datetime.now(timezone.utc)


def started(e):
    return e.get("start") and datetime.fromisoformat(e["start"].replace("Z", "+00:00")) <= now()


def upsert(lst, e, include_started):
    old = next((x for x in lst if x["id"] == e["id"]), None)
    if old:
        if old.get("final") or started(old):
            return "frozen"
        lst[lst.index(old)] = e
        return "updated"
    if started(e) and not include_started:
        return "skipped (already started)"
    lst.append(e)
    return "added"


def nfl_entries(page):
    with tempfile.TemporaryDirectory() as d:
        idx = os.path.join(d, "index.html")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), page, idx], check=True, capture_output=True)
        env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
        r = subprocess.run(["node", os.path.join(ROOT, "tools", "page_eval.js"), idx, "trackSnapshot()"], capture_output=True, text=True, env=env)
        if r.returncode or "PAGE ERRORS" in r.stderr:
            sys.exit("page evaluation failed: " + r.stderr[:500])
        return json.loads(r.stdout)


PICK = re.compile(r"^(?P<team>.+?) (?P<line>[+-]?\d+(?:\.\d+)?|PK|ML) \((?P<price>[+-]?\d+|even), (?P<book>[^)]+)\)$")


def price(x):
    return 100 if x.lower() == "even" else int(x)


def team_line(text, away, home):
    """'East Carolina -6.3' -> home margin (+ = home favored)."""
    if not text or text in ("—", "Pick'em"):
        return 0.0
    m = re.match(r"^(.*) ([+-]?\d+(?:\.\d+)?|PK)$", text.strip())
    if not m:
        return None
    v = 0.0 if m.group(2) == "PK" else float(m.group(2))
    return -v if m.group(1) == home else v


def cfb_entries(s):
    m = re.search(r"/\* CFB_DATA_START \*/const CFB=(.*?);/\* CFB_DATA_END \*/", s, re.S)
    C = json.loads(m.group(1).replace("<\\/", "</"))
    out = []
    for r in C["rows"]:
        k = re.match(r"^\w+ (\d+)/(\d+) (\d+):(\d+) (AM|PM)$", r["kickoff"])
        start = None
        if k:
            mo, dd, hh, mm, ap = k.groups()
            h = int(hh) % 12 + (12 if ap == "PM" else 0)
            yr = int(str(r.get("as_of", "2026"))[:4])
            off = -4 if (int(mo), int(dd)) < (11, 1) else -5
            start = datetime(yr, int(mo), int(dd), h, int(mm), tzinfo=timezone(timedelta(hours=off))).astimezone(timezone.utc).isoformat()
        e = {"id": f"{str(r.get('as_of','2026'))[:4]}-CFB-W{C['week']}-{r['id']}", "lg": "cfb", "wk": C["week"], "game": r["id"],
             "kick": r["kickoff"], "start": start, "away": r["away"], "home": r["home"], "at": r.get("as_of"),
             "mkt_total": r["total"], "model_total": r.get("proj_total"), "wp_home": r.get("model_home"), "bets": []}
        e["mkt_hs"] = -team_line(r["market_line"], r["away"], r["home"])
        mm_ = team_line(r["model_line"], r["away"], r["home"])
        e["model_margin"] = round(mm_, 2) if mm_ is not None else None
        for mkt, key in (("spread", "spread"), ("ml", "ml"), ("total", "total")):
            p = PICK.match(r.get(f"{key}_pick") or "")
            if not p:
                e[mkt] = None
                continue
            pk = {"price": price(p["price"]), "book": p["book"], "ev": r.get(f"{key}_ev"), "p": r.get(f"{key}_p")}
            if mkt == "total":
                pk.update(side=p["team"], line=float(p["line"]))
            elif mkt == "spread":
                pk.update(team=p["team"], line=0.0 if p["line"] == "PK" else float(p["line"]))
            else:
                pk.update(team=p["team"])
            e[mkt] = pk
            if (r.get(f"{key}_ev") or 0) >= 0.01 and (r.get(f"{key}_grade") or "Pass") != "Pass":  # Pass covers the longshot guard
                e["bets"].append(mkt)
        out.append(e)
    return out


def main():
    cmd, page = sys.argv[1], sys.argv[2]
    s, T = load(page)
    T.setdefault("nfl", []); T.setdefault("cfb", [])
    if cmd == "snapshot":
        inc = "--include-started" in sys.argv
        for e in nfl_entries(page):
            print("NFL", e["id"], upsert(T["nfl"], e, inc))
        for e in cfb_entries(s):
            print("CFB", e["id"], upsert(T["cfb"], e, inc))
        save(page, s, T)
    elif cmd == "pending":
        for lg in ("nfl", "cfb"):
            for e in T[lg]:
                if not e.get("final") and started(e):
                    print(e["id"], "|", e["away"], "@", e["home"], "|", e["kick"])
    elif cmd == "result":
        gid, a, h = sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
        for lg in ("nfl", "cfb"):
            for e in T[lg]:
                if e["id"] == gid:
                    e["final"] = {"a": a, "h": h}
                    save(page, s, T)
                    print("recorded", gid, f"{e['away']} {a} @ {e['home']} {h}")
                    return
        sys.exit("id not found: " + gid)
    elif cmd == "summary":
        print(json.dumps({lg: {"logged": len(T[lg]), "final": sum(1 for e in T[lg] if e.get("final"))} for lg in ("nfl", "cfb")}))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
