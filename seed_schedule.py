"""
One-time seed: insert Open division 2025-2026 schedule data into the schedule table.
Run from project root: python seed_schedule.py
"""
import os
import sqlite3

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))
LEVEL = "open"
YEAR = 2025
LEAGUE = "handicap"

# (week, date_range, team1, team2, bye, team1_players, team2_players, handicap, games1, games2)
ROWS = [
    (1, "Jan 18–Jan 24", "Old and in the way", "Even Older and Grumpier", None, "Ros Bowers, Teddy Damgard", "Jim Bonbright, Sanjay Hinduja", "2-0", 2, 3),
    (1, "Jan 18–Jan 24", "El Mustachios", "Fatty and Friends", None, "Mark Davis, John Street", "Scott Harrison, Ned Sinnott", "0-5", 3, 1),
    (1, "Jan 18–Jan 24", "Mack Attack", "All the right Angles", None, "Andy Mack, David Shepardson", "Robert Angle, Charles Kempe", "2-0", 3, 1),
    (1, "Jan 18–Jan 24", None, None, "Team Nitro", None, None, None, None, None),
    (2, "Jan 25–Jan 31", "Old and in the way", "El Mustachios", None, "Teddy Damgard, Monty Geho", "Tommy Richards, Mark Davis", "7-0", 2, 3),
    (2, "Jan 25–Jan 31", "Even Older and Grumpier", "Mack Attack", None, "Jim Davis, Sanjay Hinduja", "Michael Halloran, Jon Rasich", "2-0", 3, 2),
    (2, "Jan 25–Jan 31", "Fatty and Friends", "Team Nitro", None, None, None, None, None, None),
    (2, "Jan 25–Jan 31", None, None, "All the right Angles", None, None, None, None, None),
    (3, "Feb 1–Feb 7", "Old and in the way", "Fatty and Friends", None, None, None, None, None, None),
    (3, "Feb 1–Feb 7", "Even Older and Grumpier", "All the right Angles", None, "Jim Bonbright, Jim Davis", "George Stephenson, Charles Kempe", "4-0", 2, 3),
    (3, "Feb 1–Feb 7", "El Mustachios", "Team Nitro", None, "Tommy Richards and Jimmy Cooke", "Berkeley Edmunds and Frank De Venoge", "0-4", 2, 3),
    (3, "Feb 1–Feb 7", None, None, "Mack Attack", None, None, None, None, None),
    (4, "Feb 8–Feb 14", "Old and in the way", "Mack Attack", None, "Ros Bowers and Monty Geho", "Andy Mack and Michael Halloran", "3-0", 0, 3),
    (4, "Feb 8–Feb 14", "Even Older and Grumpier", "Team Nitro", None, "Jim Davis and Sanjay Hinduja", "Josh Wishnack, Teddy Damgard", "0-6", 2, 3),
    (4, "Feb 8–Feb 14", "Fatty and Friends", "All the right Angles", None, "Ned Sinnott and Matt Chriss", "George Stephenson and Charles Kempe", "4-0", 1, 3),
    (4, "Feb 8–Feb 14", None, None, "El Mustachios", None, None, None, None, None),
    (5, "Feb 15–Feb 21", "Old and in the way", "All the right Angles", None, "Eddie O'Leary, Teddy Damgard", "Robert Angle, Jimmy Meadows", "2-0", 1, 3),
    (5, "Feb 15–Feb 21", "Even Older and Grumpier", "El Mustachios", None, "Jim Davis, Dean King", "Tommy Richards, Michael Halloran", "5-0", 1, 3),
    (5, "Feb 15–Feb 21", "Mack Attack", "Team Nitro", None, "Andy Mack and David Shepardson", "Manoli Loupassi and Dean King", "0-6", 3, 1),
    (5, "Feb 15–Feb 21", None, None, "Fatty and Friends", None, None, None, None, None),
    (6, "Feb 22–Feb 28", "Old and in the way", "Team Nitro", None, "Ros Bowers and Eddie O'Leary", "Frank De Venoge and Berkeley Edmunds", "0-7", 0, 3),
    (6, "Feb 22–Feb 28", "El Mustachios", "All the right Angles", None, "Tommy Richards and Mark Davis", "George Stephenson and Charles Kempe", "5-0", 2, 3),
    (6, "Feb 22–Feb 28", "Fatty and Friends", "Mack Attack", None, "Scott Harrison and Ned Sinnott", "David Shepardson and Michael Halloran", "0-3", 3, 2),
    (6, "Feb 22–Feb 28", None, None, "Even Older and Grumpier", None, None, None, None, None),
    (7, "Mar 1–Mar 7", "Even Older and Grumpier", "Fatty and Friends", None, "Jim Bonbright and Jim Davis", "Ned Sinnott and Matt Chriss", "2-0", 3, 2),
    (7, "Mar 1–Mar 7", "El Mustachios", "Mack Attack", None, "Michael Jarvis and Jimmy Cooke", "Michael Halloran and Jon Rasich", "0-0", 2, 3),
    (7, "Mar 1–Mar 7", "All the right Angles", "Team Nitro", None, "Robert Angle and George Stephenson", "Josh Wishnack and Manoli Loupassi", "0-4", 3, 1),
    (7, "Mar 1–Mar 7", None, None, "Old and in the way", None, None, None, None, None),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    # Clear existing open 2025 schedule and scores so this run replaces them
    conn.execute(
        "DELETE FROM schedule WHERE level = ? AND (year = ? OR year IS NULL)",
        (LEVEL, YEAR),
    )
    conn.execute(
        "DELETE FROM scores WHERE league = ? AND level = ? AND (year = ? OR year IS NULL)",
        (LEAGUE, LEVEL, YEAR),
    )
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
    # Insert into scores for rows with game results so standings update
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
    n_scores = sum(1 for r in ROWS if r[2] and r[3] and r[8] is not None and r[9] is not None)
    print(f"Inserted {len(ROWS)} schedule rows and {n_scores} scores for {LEVEL} {YEAR}. Standings updated.")


if __name__ == "__main__":
    main()
