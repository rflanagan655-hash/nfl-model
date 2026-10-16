"""Merge cfbstats.com Total Offense / Total Defense tables into ratings.json.

Usage: python3 ingest_yards.py raw/tot_off.txt raw/tot_def.txt ratings.json
Each raw line: Team|G|Plays|Yards|Yards/Play|Yards/G (cfbstats.com national team leaders, category 10,
offense and defense pages). Adds per team: y_games, plays_off, yds_off, plays_def, yds_def and national ranks
(ypp_off_rk, ypp_def_rk, ypg_off_rk, ypg_def_rk; rank 1 = most yards gained / fewest allowed), and league
averages ypp_avg (yards per play) and plays_pg_avg (offensive plays per team per game).
"""
import json, sys

ALIAS = {"Miami (FL)": "Miami"}


def read(path):
    out = {}
    for ln in open(path):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        n, g, pl, y, _, _ = ln.split("|")
        out[ALIAS.get(n, n)] = dict(g=int(g), plays=int(pl), yds=int(y.replace(",", "")))
    return out


def ranks(D, key, reverse):
    order = sorted(D, key=key, reverse=reverse)
    return {k: i + 1 for i, k in enumerate(order)}


def main():
    O, D, path = read(sys.argv[1]), read(sys.argv[2]), sys.argv[3]
    R = json.load(open(path))
    r_ypp_o = ranks(O, lambda k: O[k]["yds"] / O[k]["plays"], True)
    r_ypg_o = ranks(O, lambda k: O[k]["yds"] / O[k]["g"], True)
    r_ypp_d = ranks(D, lambda k: D[k]["yds"] / D[k]["plays"], False)
    r_ypg_d = ranks(D, lambda k: D[k]["yds"] / D[k]["g"], False)
    miss = []
    for name, t in R["teams"].items():
        if name not in O or name not in D:
            miss.append(name); continue
        t.update(y_games=O[name]["g"], plays_off=O[name]["plays"], yds_off=O[name]["yds"],
                 plays_def=D[name]["plays"], yds_def=D[name]["yds"],
                 ypp_off_rk=r_ypp_o[name], ypg_off_rk=r_ypg_o[name], ypp_def_rk=r_ypp_d[name], ypg_def_rk=r_ypg_d[name])
    R["league"]["ypp_avg"] = round(sum(v["yds"] for v in O.values()) / sum(v["plays"] for v in O.values()), 3)
    R["league"]["plays_pg_avg"] = round(sum(v["plays"] for v in O.values()) / sum(v["g"] for v in O.values()), 2)
    R["league"]["y_teams"] = len(O)
    R["sources"]["yo"] = {"title": "Total offense (yards per play, yards per game), 2026 — cfbstats.com",
                          "url": "https://cfbstats.com/2026/leader/national/team/offense/split01/category10/sort01.html"}
    R["sources"]["yd"] = {"title": "Total defense (yards per play, yards per game allowed), 2026 — cfbstats.com",
                          "url": "https://cfbstats.com/2026/leader/national/team/defense/split01/category10/sort01.html"}
    json.dump(R, open(path, "w"), indent=1)
    print(f"{len(R['teams']) - len(miss)} teams updated from {len(O)} FBS rows; league {R['league']['ypp_avg']} yds/play, "
          f"{R['league']['plays_pg_avg']} plays/g; missing: {', '.join(miss) or 'none'}")


if __name__ == "__main__":
    main()
