# Best Touchdown Bets data

`build_td.py` turns the raw season files here into the `TD_DATA` block in the NFL MODEL page:

    python3 td/build_td.py <page.html> "<as-of text>" <Thursday of the NFL week, YYYY-MM-DD> [-04:00 | -05:00]

| File | Source | Refresh |
|---|---|---|
| raw_rb.txt `Name|TEAM|ATT|RushTD|TGT|RecTD|G` | fantasypros.com/nfl/stats/rb.php | Tuesday |
| raw_wr.txt `Name|(TEAM)|TGT|REC|RecTD|RushATT|RushTD|G` | fantasypros.com/nfl/stats/wr.php | Tuesday |
| raw_te.txt `Name|TEAM|TGT|REC|RecTD|G` | fantasypros.com/nfl/stats/te.php | Tuesday |
| raw_qb.txt `Name|TEAM|PassATT|PassTD|RushATT|RushTD|G` | fantasypros.com/nfl/stats/qb.php | Tuesday |
| team_def_off.txt `OFF/DEF Team name|EPA|EPA pass|EPA rush|pass TD|rush TD` | sumersports.com/teams/offensive/ and /defensive/ | Tuesday |
| rz_snap.txt `RZC/RZT/SNAP Name|TEAM|value` | rosteraudit.com/stats/rz-carry-share/rb/, rz-target-share/wr/ and /te/, snap-pct/rb/, /wr/, /te/ | Tuesday |
| injuries.txt `Name|TEAM|P(active)|status` | official/team injury reports | daily |

The page's own BASE_POOL statuses (refreshed daily) override injuries.txt for players in both.
