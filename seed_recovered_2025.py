"""
Seed 2025 handicap Open/Main scores and schedule from recovered local data.
Use this to restore the latest scores after a deploy or DB reset (e.g. on Render).

Run from project root: python seed_recovered_2025.py

Recovered: 29 scores (13 open, 9 main, 7 main week 7 added) as of recovery.
"""
import os
import sqlite3

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))
LEAGUE = "handicap"
YEAR = 2025

WEEK_DATE_RANGES = {
    1: "Jan 18–Jan 24",
    2: "Jan 25–Jan 31",
    3: "Feb 1–Feb 7",
    4: "Feb 8–Feb 14",
    5: "Feb 15–Feb 21",
    6: "Feb 22–Feb 28",
    7: "Mar 1–Mar 7",
}

# Recovered scores: (level, week, team1, team2, games1, games2, team1_players, team2_players, handicap)
SCORES = [
    ("main", 1, "The Double Troubles", "The Boast Beasts", 3, 1, "Peter Thacker and Tom Mitchell", "Skylyr Phillips and Nick Farrell", "0-10"),
    ("main", 2, "Drop Shotz", "The Boast Beasts", 2, 3, "Mukul Paithane and Robert Gentil", "Skylyr Phillips and Deesh Bhattal", "0-5"),
    ("main", 2, "The Double Troubles", "Tin and Tonic", 3, 1, "Tom & Bob", "Moses & Alan", "0-3"),
    ("main", 3, "The Double Troubles", "Drop Shotz", 0, 3, "Peter/Heidi", "Jack/Mukul", "0-2"),
    ("main", 3, "Tin and Tonic", "The Boast Beasts", 3, 1, "Matt Rho and Billy Miller", "Skylyr and Deesh", "0-9"),
    ("main", 5, "Drop Shotz", "Tin and Tonic", 3, 2, "Jack & Austin", "Trey & Billy", "7-0"),
    ("main", 5, "The Double Troubles", "The Boast Beasts", 0, 3, "Heidi Stevenson, Bob Reynolds", "Nick Farrell, Deesh Bhattal", "0-7"),
    ("main", 6, "Drop Shotz", "The Boast Beasts", 3, 1, "Jack Hager, Robert Gentil", "Skye Phillips, Nick Farrell", "0 / 5"),
    ("main", 6, "The Double Troubles", "Tin and Tonic", 3, 2, "Bob Reynolds, Peter Thacker", "Trey Packard, Billy Mitchell", "0 / 1"),
    ("main", 7, "Tin and Tonic", "The Boast Beasts", 3, 2, "Billy Miller, Alan Stone", "Skye Phillips, Nick Farrell", "0 / 8"),
    ("open", 1, "El Mustachios", "Fatty and Friends", 3, 1, "Mark Davis, John Street", "Scott Harrison, Ned Sinnott", "0-5"),
    ("open", 1, "Mack Attack", "All the right Angles", 3, 1, "Andy Mack, Dave Shepardson", "Robert Angle, Charles Kempe", "2-0"),
    ("open", 1, "Old and in the way", "Even Older and Grumpier", 2, 3, "Ros Bowers, Teddy Damgard", "Jim Bonbright, Sanjay Hinduja", "2 / 0"),
    ("open", 2, "Even Older and Grumpier", "Mack Attack", 3, 2, "Jim Davis, Sanjay Hinduja", "Michael Halloran, Jon Rasich", "2-0"),
    ("open", 2, "Old and in the way", "El Mustachios", 2, 3, "Teddy Damgard, Monty Geho", "Tommy Richards, Mark Davis", "7-0"),
    ("open", 3, "El Mustachios", "Team Nitro", 2, 3, "Tommy Richards, Jimmy Cooke", "Berkeley Edmunds, Frank De Venoge", "0 / 4"),
    ("open", 3, "Even Older and Grumpier", "All the right Angles", 2, 3, "Jim Bonbright, Jim Davis", "George Stephenson, Charles Kempe", "4-0"),
    ("open", 4, "Even Older and Grumpier", "Team Nitro", 2, 3, "Jim Davis, Sanjay Hinduja", "Josh Wishnack, Teddy Damgard", "0-6"),
    ("open", 4, "Fatty and Friends", "All the right Angles", 1, 3, "Ned Sinnott, Matt Chriss", "George Stephenson, Charles Kempe", "4-0"),
    ("open", 4, "Old and in the way", "Mack Attack", 0, 3, "Ros Bowers, Monty Geho", "Andy Mack, Michael Halloran", "3-0"),
    ("open", 5, "Even Older and Grumpier", "El Mustachios", 1, 3, "Jim Davis, Dean King", "Tommy Richards, Michael Halloran", "5-0"),
    ("open", 5, "Mack Attack", "Team Nitro", 3, 1, "Andy Mack, Dave Shepardson", "Manoli Loupassi, Dean King", "0-6"),
    ("open", 5, "Old and in the way", "All the right Angles", 1, 3, "Eddie O'Leary, Teddy Damgard", "Robert Angle, Jimmy Meadows", "2-0"),
    ("open", 6, "El Mustachios", "All the right Angles", 2, 3, "Tommy Richards, Mark Davis", "George Stephenson, Charles Kempe", "0 / 5"),
    ("open", 6, "Fatty and Friends", "Mack Attack", 3, 2, "Scott Harrison, Ned Sinnott", "Dave Shepardson, Michael Halloran", "0-3"),
    ("open", 6, "Old and in the way", "Team Nitro", 0, 3, "Ros Bowers, Eddie O'Leary", "Frank De Venoge, Berkeley Edmunds", "0 / 7"),
    ("open", 7, "All the right Angles", "Team Nitro", 3, 1, "Robert Angle, George Stephenson", "Josh Wishnack, Manoli Loupassi", "0 / 4"),
    ("open", 7, "El Mustachios", "Mack Attack", 2, 3, "Jimmy Cooke, Michael Jarvis", "Michael Halloran, Jon Rasich", "0 / 0"),
    ("open", 7, "Even Older and Grumpier", "Fatty and Friends", 3, 2, "Jim Bonbright, Jim Davis", "Ned Sinnott, Matt Chriss", "2 / 0"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    # Clear existing 2025 handicap scores and schedule so we can restore cleanly
    conn.execute(
        "DELETE FROM scores WHERE league = ? AND level IN ('open', 'main') AND (year = ? OR year IS NULL)",
        (LEAGUE, YEAR),
    )
    conn.execute(
        "DELETE FROM schedule WHERE level IN ('open', 'main') AND (year = ? OR year IS NULL)",
        (YEAR,),
    )
    for s in SCORES:
        level, week, team1, team2, games1, games2, team1_players, team2_players, handicap = s
        conn.execute(
            """INSERT INTO scores (league, level, week, handicap, team1, team2, games1, games2, team1_players, team2_players, year)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (LEAGUE, level, week, handicap, team1, team2, games1, games2, team1_players, team2_players, YEAR),
        )
        score_str = f"{games1}-{games2}"
        winner = team1 if games1 > games2 else (team2 if games2 > games1 else None)
        date_range = WEEK_DATE_RANGES.get(week, "")
        conn.execute(
            """INSERT INTO schedule (level, week, date_range, team1, team2, bye, team1_players, team2_players, handicap, score, winner, year)
               VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)""",
            (level, week, date_range, team1, team2, team1_players, team2_players, handicap, score_str, winner, YEAR),
        )
    conn.commit()
    conn.close()
    print(f"Restored {len(SCORES)} scores and schedule rows for {YEAR}.")


if __name__ == "__main__":
    main()
