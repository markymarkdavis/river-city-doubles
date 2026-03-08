"""
Pull schedule and scores from the hosted River City Doubles API into the local database.
Run from project root:
  RCD_HOST=https://your-flask-service.onrender.com python pull_from_hosted.py
  # or
  python pull_from_hosted.py --host https://your-flask-service.onrender.com
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))
LEAGUE = "handicap"
YEAR = 2025


def fetch_json(base_url: str, path: str) -> dict | list:
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    parser = argparse.ArgumentParser(description="Pull data from hosted River City Doubles API")
    parser.add_argument("--host", help="Base URL of hosted API (e.g. https://river-city-doubles.onrender.com)")
    args = parser.parse_args()
    base = args.host or os.environ.get("RCD_HOST", "").strip()
    if not base:
        print("Set RCD_HOST or pass --host with the hosted API base URL.")
        print("Example: RCD_HOST=https://river-city-doubles.onrender.com python pull_from_hosted.py")
        sys.exit(1)

    print(f"Pulling from {base}...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        years = fetch_json(base, "/api/years")
        year = int(years[-1]) if years else YEAR
    except Exception as e:
        print(f"Could not fetch years: {e}")
        year = YEAR

    for level in ("open", "main"):
        try:
            rows = fetch_json(base, f"/api/schedule?level={level}&year={year}")
        except Exception as e:
            print(f"Could not fetch schedule for {level}: {e}")
            continue

        # Deduplicate by (week, team pair); prefer the row that has a score
        by_key = {}
        for r in rows:
            t1, t2 = r.get("team1") or "", r.get("team2") or ""
            key = (r.get("week"), tuple(sorted([t1, t2])))
            has_score = bool((r.get("score") or "").strip())
            existing_in_batch = by_key.get(key)
            if existing_in_batch is None or (has_score and not (existing_in_batch.get("score") or "").strip()):
                by_key[key] = r

        for r in by_key.values():
            t1, t2 = r.get("team1") or "", r.get("team2") or ""
            existing = conn.execute(
                """SELECT id FROM schedule WHERE level = ? AND week = ? AND (year = ? OR year IS NULL)
                   AND ((team1 = ? AND team2 = ?) OR (team1 = ? AND team2 = ?))""",
                (level, r["week"], year, t1, t2, t2, t1),
            ).fetchone()
            row = (
                level,
                r["week"],
                (r.get("date_range") or "").strip() or None,
                t1 or None,
                t2 or None,
                (r.get("bye") or "").strip() or None,
                (r.get("team1_players") or "").strip() or None,
                (r.get("team2_players") or "").strip() or None,
                (r.get("handicap") or "").strip() or None,
                (r.get("score") or "").strip() or None,
                (r.get("winner") or "").strip() or None,
                year,
            )
            if existing:
                conn.execute(
                    """UPDATE schedule SET date_range=?, team1=?, team2=?, bye=?, team1_players=?,
                       team2_players=?, handicap=?, score=?, winner=?, year=? WHERE id=?""",
                    (*row[2:], existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO schedule (level, week, date_range, team1, team2, bye, team1_players,
                       team2_players, handicap, score, winner, year)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row,
            )
        print(f"  Schedule {level}: {len(by_key)} rows")

    # Backfill scores from schedule rows that have scores
    for level in ("open", "main"):
        conn.execute(
            "DELETE FROM scores WHERE league = ? AND level = ? AND (year = ? OR year IS NULL)",
            (LEAGUE, level, year),
        )
        rows = conn.execute(
            """SELECT week, team1, team2, team1_players, team2_players, handicap, score
               FROM schedule WHERE level = ? AND (year = ? OR year IS NULL)
               AND team1 IS NOT NULL AND team2 IS NOT NULL AND score IS NOT NULL AND score != ''""",
            (level, year),
        ).fetchall()
        count = 0
        for r in rows:
            score = r["score"].strip()
            parts = score.split("-")
            if len(parts) != 2:
                continue
            try:
                games1, games2 = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            conn.execute(
                """INSERT INTO scores (league, level, week, handicap, team1, team2, games1, games2,
                   team1_players, team2_players, year)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (LEAGUE, level, r["week"], r["handicap"], r["team1"], r["team2"], games1, games2,
                r["team1_players"], r["team2_players"], year),
            )
            count += 1
        print(f"  Scores {level}: {count} backfilled")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
