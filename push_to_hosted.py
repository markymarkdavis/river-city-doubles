"""
Push scores from your local database to the hosted River City Doubles API.
Use this so schedule/score updates you make locally are reflected on the hosted site.

Run from project root:
  RCD_HOST=https://river-city-doubles.onrender.com python push_to_hosted.py
  # or
  python push_to_hosted.py --host https://river-city-doubles.onrender.com
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))
LEAGUE = "handicap"


def main():
    parser = argparse.ArgumentParser(
        description="Push local scores to hosted River City Doubles API so the hosted site reflects your updates."
    )
    parser.add_argument("--host", help="Base URL of hosted API (e.g. https://river-city-doubles.onrender.com)")
    args = parser.parse_args()
    base = args.host or os.environ.get("RCD_HOST", "").strip().rstrip("/")
    if not base:
        print("Set RCD_HOST or pass --host with the hosted API base URL.")
        print("Example: RCD_HOST=https://river-city-doubles.onrender.com python push_to_hosted.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT league, level, week, team1, team2, games1, games2, team1_players, team2_players, handicap, year
           FROM scores WHERE league = ? AND level IN ('open', 'main') ORDER BY level, week, team1""",
        (LEAGUE,),
    ).fetchall()
    conn.close()

    if not rows:
        print("No handicap open/main scores in local database. Nothing to push.")
        return

    h1, h2 = None, None
    ok = 0
    err = 0
    for r in rows:
        handicap = (r["handicap"] or "").strip()
        if " / " in handicap:
            parts = handicap.split(" / ", 1)
            h1, h2 = (parts[0].strip() or None), (parts[1].strip() if len(parts) > 1 else None)
        else:
            h1, h2 = (handicap or None), None

        payload = {
            "league": r["league"],
            "level": r["level"],
            "week": int(r["week"]),
            "team1": r["team1"],
            "team2": r["team2"],
            "games1": int(r["games1"]),
            "games2": int(r["games2"]),
            "team1_players": r["team1_players"] or None,
            "team2_players": r["team2_players"] or None,
            "handicap_team1": h1,
            "handicap_team2": h2,
            "year": int(r["year"]) if r["year"] is not None else None,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            base + "/api/scores",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if 200 <= resp.getcode() < 300:
                    ok += 1
                else:
                    err += 1
        except Exception as e:
            print(f"  Failed {r['level']} w{r['week']} {r['team1']} vs {r['team2']}: {e}")
            err += 1
    print(f"Pushed to {base}: {ok} ok, {err} failed.")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
