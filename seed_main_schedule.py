"""
Seed Main handicap division 2025-2026 schedule and scores.
Run from project root: python seed_main_schedule.py
"""
import os
import sqlite3

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))
LEVEL = "main"
YEAR = 2025
LEAGUE = "handicap"

# (week, date_range, team1, team2, bye, team1_players, team2_players, handicap, games1, games2)
ROWS = [
    (1, "Jan 18–Jan 24", "The Double Troubles", "The Boast Beasts", None, "Peter Thacker and Tom Mitchell", "Skylyr Phillips and Nick Farrell", "0-10", 3, 1),
    (1, "Jan 18–Jan 24", "Drop Shotz", "Tin and Tonic", None, None, None, None, None, None),
    (2, "Jan 25–Jan 31", "The Double Troubles", "Tin and Tonic", None, "Tom & Bob", "Moses & Alan", "0-3", 3, 1),
    (2, "Jan 25–Jan 31", "Drop Shotz", "The Boast Beasts", None, "Mukul Paithane and Robert Gentil", "Skylyr Phillips and Deesh Bhattal", "0-5", 2, 3),
    (3, "Feb 1–Feb 7", "The Double Troubles", "Drop Shotz", None, "Peter/Heidi", "Jack/Mukul", "0-2", 0, 3),
    (3, "Feb 1–Feb 7", "Tin and Tonic", "The Boast Beasts", None, "Matt Rho and Billy Miller", "Skylyr and Deesh", "0-9", 3, 1),
    (4, "Feb 8–Feb 14", None, None, "BYE WEEK", None, None, None, None, None),
    (5, "Feb 15–Feb 21", "The Double Troubles", "The Boast Beasts", None, "Heidi Stevenson, Bob Reynolds", "Nick Farrell, Deesh Bhattal", "0-7", 0, 3),
    (5, "Feb 15–Feb 21", "Drop Shotz", "Tin and Tonic", None, "Jack & Austin", "Trey & Billy", "7-0", 3, 2),
    (6, "Feb 22–Feb 28", "The Double Troubles", "Tin and Tonic", None, "Bob & Peter", "Trey & Billy", "0-1", 3, 2),
    (6, "Feb 22–Feb 28", "Drop Shotz", "The Boast Beasts", None, None, None, None, None, None),
    (7, "Mar 1–Mar 7", "The Double Troubles", "Drop Shotz", None, None, None, None, None, None),
    (7, "Mar 1–Mar 7", "Tin and Tonic", "The Boast Beasts", None, None, None, None, None, None),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    for r in ROWS:
        week, date_range, team1, team2, bye, team1_players, team2_players, handicap, games1, games2 = r
        if games1 is not None and games2 is not None:
            score = f"{games1}-{games2}"
            winner = team1 if games1 > games2 else (team2 if team2 and games2 > games1 else None)
        else:
            score = None
            winner = None
        conn.execute(
            """INSERT INTO schedule (level, week, date_range, team1, team2, bye, team1_players, team2_players, handicap, score, winner, year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (LEVEL, week, date_range or None, team1, team2, bye, team1_players, team2_players, handicap, score, winner, YEAR),
        )
    # Insert into scores for rows with game results (so standings update)
    for r in ROWS:
        week, date_range, team1, team2, bye, team1_players, team2_players, handicap, games1, games2 = r
        if team1 and team2 and games1 is not None and games2 is not None:
            conn.execute(
                """INSERT INTO scores (league, level, week, handicap, team1, team2, games1, games2, team1_players, team2_players, year)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (LEAGUE, LEVEL, week, handicap, team1, team2, games1, games2, team1_players, team2_players, YEAR),
            )
    conn.commit()
    conn.close()
    print(f"Inserted {len(ROWS)} schedule rows and {sum(1 for r in ROWS if r[1] and r[2] and r[8] is not None and r[9] is not None)} scores for {LEVEL} {YEAR}.")


if __name__ == "__main__":
    main()
