"""
Backfill the scores table from schedule rows that have a score.
This updates the standings (which are computed from scores).
Run from project root: python backfill_standings_from_schedule.py
"""
import os
import sqlite3

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))
LEVEL = "open"
YEAR = 2025
LEAGUE = "handicap"


def main():
    conn = sqlite3.connect(DB_PATH)
    # Remove existing open 2025 scores so we don't duplicate when re-running
    conn.execute(
        "DELETE FROM scores WHERE league = ? AND level = ? AND (year = ? OR year IS NULL)",
        (LEAGUE, LEVEL, YEAR),
    )
    # Get schedule rows that have a score
    rows = conn.execute(
        """SELECT week, team1, team2, team1_players, team2_players, handicap, score
           FROM schedule
           WHERE level = ? AND (year = ? OR year IS NULL) AND team1 IS NOT NULL AND team2 IS NOT NULL AND score IS NOT NULL AND score != ''""",
        (LEVEL, YEAR),
    ).fetchall()
    count = 0
    for r in rows:
        week, team1, team2, team1_players, team2_players, handicap, score = r
        parts = score.strip().split("-")
        if len(parts) != 2:
            continue
        try:
            games1, games2 = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        conn.execute(
            """INSERT INTO scores (league, level, week, handicap, team1, team2, games1, games2, team1_players, team2_players, year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (LEAGUE, LEVEL, week, handicap, team1, team2, games1, games2, team1_players, team2_players, YEAR),
        )
        count += 1
    conn.commit()
    conn.close()
    print(f"Backfilled {count} scores from schedule for {LEVEL} {YEAR}. Standings will now reflect these results.")


if __name__ == "__main__":
    main()
