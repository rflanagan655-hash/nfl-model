"""Prop Tracker: log the week's Top 10 props (EV between +$0 and +$3 per $100) and grade them against the player's actual stat.

The ledger lives in the page between /* PROPTRACK_DATA_START */ and /* PROPTRACK_DATA_END */ and is mirrored to
tracker/props.json. It is kept apart from the game-lines Model Tracker (tools/track.py). Every command edits <page.html> in place.

Which ten count: the Top 10 list as it stood at the last snapshot before the week's first Sunday kickoff. Until then each
snapshot replaces the week's list; after that the week is locked. (The page's list only shows games not yet kicked off, so
Thursday-night props are not part of the logged ten.)

  python3 tools/prop_track.py snapshot <page.html>             log this week's Top 10 (replaced until the Sunday lock)
  python3 tools/prop_track.py pending <page.html>              logged props whose game has started and still need the stat
  python3 tools/prop_track.py result <page.html> <id> <stat>   record the player's actual stat (anytime TD: number of TDs scored;
                                                               use "dnp" if he didn't play: the bet is void and counts as a push)
  python3 tools/prop_track.py summary <page.html>              print the record
"""
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = re.compile(r"/\* PROPTRACK_DATA_START \*/const PROPTRACK=(.*?);/\* PROPTRACK_DATA_END \*/", re.S)
ET = timezone(timedelta(hours=-5))


def load(page):
    s = open(page, encoding="utf-8").read()
    m = MARK.search(s)
    if not m:
        sys.exit("PROPTRACK markers not found")
    return s, json.loads(m.group(1).replace("<\\/", "</"))


def save(page, s, T):
    T["updated"] = datetime.now(ET).strftime("%a %b %d, %Y %I:%M %p ET").replace(" 0", " ")
    blob = "/* PROPTRACK_DATA_START */const PROPTRACK=" + json.dumps(T, separators=(",", ":")).replace("</", "<\\/") + ";/* PROPTRACK_DATA_END */"
    s = MARK.sub(lambda m: blob, s)
    open(page, "w", encoding="utf-8").write(s)
    os.makedirs(os.path.join(ROOT, "tracker"), exist_ok=True)
    json.dump(T, open(os.path.join(ROOT, "tracker", "props.json"), "w"), indent=1)


def ts(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


def page_snapshot(page):
    with tempfile.TemporaryDirectory() as d:
        idx = os.path.join(d, "index.html")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), page, idx], check=True, capture_output=True)
        env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
        r = subprocess.run(["node", os.path.join(ROOT, "tools", "page_eval.js"), idx, "propTrackSnapshot()"], capture_output=True, text=True, env=env)
        if r.returncode or "PAGE ERRORS" in r.stderr:
            sys.exit("page evaluation failed: " + r.stderr[:500])
        return json.loads(r.stdout)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, page = sys.argv[1], sys.argv[2]
    s, T = load(page)
    T.setdefault("props", [])
    T.setdefault("weeks", {})
    if cmd == "snapshot":
        S = page_snapshot(page)
        wk, now = str(S["wk"]), datetime.now(timezone.utc)
        lock = S.get("lock")
        if lock and now >= ts(lock):
            print(f"Week {wk} is locked (first Sunday kickoff {lock}); list not changed")
            return
        T["props"] = [p for p in T["props"] if str(p["wk"]) != wk] + S["top"]
        T["weeks"][wk] = {"lock": lock, "at": S.get("at"), "logged": now.isoformat(timespec="minutes")}
        save(page, s, T)
        for p in S["top"]:
            print(p["id"], f"{p['side']} {p['line']} {p['m']}", p["price"], p["book"], f"EV {p['ev']}")
        print(f"Week {wk}: logged {len(S['top'])} props (replaced until {lock})")
    elif cmd == "pending":
        now = datetime.now(timezone.utc)
        for p in T["props"]:
            if p.get("actual") is None and not p.get("dnp") and p.get("start") and ts(p["start"]) <= now:
                print(p["id"], "|", p["name"], p["side"], p["line"], p["m"], "|", p["matchup"], p["kick"])
    elif cmd == "result":
        pid, v = sys.argv[3], sys.argv[4]
        for p in T["props"]:
            if p["id"] == pid:
                if v.lower() == "dnp":
                    p["dnp"], p["actual"] = True, None
                else:
                    p.pop("dnp", None)
                    p["actual"] = float(v)
                    if p["actual"].is_integer():
                        p["actual"] = int(p["actual"])
                save(page, s, T)
                print("recorded", pid, v)
                return
        sys.exit("id not found: " + pid)
    elif cmd == "summary":
        w = l = pu = 0
        units = 0.0
        for p in T["props"]:
            if p.get("dnp"):
                pu += 1
                continue
            a = p.get("actual")
            if a is None:
                continue
            won = a > p["line"] if p["side"] == "over" else a < p["line"]
            if a == p["line"]:
                pu += 1
            elif won:
                w += 1
                units += p["price"] / 100 if p["price"] > 0 else 100 / -p["price"]
            else:
                l += 1
                units -= 1
        print(json.dumps({"logged": len(T["props"]), "record": f"{w}-{l}-{pu}", "units": round(units, 2)}))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
