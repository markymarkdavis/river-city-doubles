"""
Box league rosters for server-side logic (must stay aligned with static/app.js).

Used to decide which notify_box subscribers belong to which box for a season year.
"""
from __future__ import annotations

# Default season (e.g. 2025): full roster per box tab.
BOX_PLAYERS: dict[str, dict[str, str]] = {
    "Foo Fighters": {
        "A": "Mark Davis",
        "B": "Josh Wishnack",
        "C": "Scott Harrison",
        "D": "John Street",
        "E": "Rob Long",
        "F": "Robert Angle",
    },
    "Pink Floyd": {
        "A": "Sanjay Hinduja",
        "B": "Ros Bowers",
        "C": "Tommy Richards",
        "D": "Shelton Horsley",
        "E": "Grant Stevens",
        "F": "Jon Rasich",
    },
    "Dire Straits": {
        "A": "Jimmy Meadows",
        "B": "Jim Bonbright",
        "C": "Spencer Williamson",
        "D": "Teddy Damgard",
        "E": "Jack Hager",
        "F": "Alan Burke",
    },
    "Metallica": {
        "A": "Jim Maxwell",
        "B": "Alan Stone",
        "C": "Moses Maxfield",
        "D": "Robert Gentil",
        "E": "Nick Farrell",
        "F": "Deesh Bhattal",
    },
    "Nirvana": {
        "A": "Matt Rho",
        "B": "Tom Mitchell",
        "C": "Billy Miller",
        "D": "Mukul Paithane",
        "E": "Austin Brockenbough",
        "F": "Peter Thacker",
    },
    "Fleetwood Mac": {
        "A": "Bob Reynolds",
        "B": "BT Thornton",
        "C": "Nitin Sethi",
        "D": "Heidi Stevenson",
        "E": "Skylyr Phillips",
        "F": "Trey Packard",
    },
    "Guns N' Roses": {
        "A": "Jimmy Cooke",
        "B": "Frank De Venoge",
        "C": "David Shepardson",
        "D": "Dean King",
        "E": "Matt Chriss",
        "F": "Berkeley Edmunds",
    },
    "Pearl Jam": {
        "A": "Andy Mack",
        "B": "Eddie O'Leary",
        "C": "Jim Davis",
        "D": "Monty Geho",
        "E": "Charles Kempe",
        "F": "Manoli Loupassi",
    },
    "Deep Purple": {
        "A": "George Stephenson",
        "B": "Rand Robins",
        "C": "Michael Jarvis",
        "D": "Jeff Clarke",
        "E": "Michael Halloran",
        "F": "Ned Sinnott",
    },
}

# Years with explicit per-box overrides only (no fallback to BOX_PLAYERS for missing teams).
BOX_PLAYERS_BY_YEAR: dict[int, dict[str, dict[str, str]]] = {
    2026: {
        "Foo Fighters": {
            "A": "Mark Davis",
            "B": "Jim Davis",
            "C": "Sanjay Hinduja",
            "D": "Grant Stevens",
            "E": "Andy Mack",
            "F": "Eddie O'Leary",
        },
    },
}


def year_uses_explicit_box_list(year: int) -> bool:
    return year in BOX_PLAYERS_BY_YEAR


def get_box_roster_dict(team: str, year: int) -> dict[str, str]:
    """Mirror static/app.js getBoxPlayersForYear (sheet roster only)."""
    y = int(year)
    if year_uses_explicit_box_list(y):
        return dict(BOX_PLAYERS_BY_YEAR.get(y, {}).get(team) or {})
    return dict(BOX_PLAYERS.get(team) or {})
