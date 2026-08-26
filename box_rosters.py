"""
Box league rosters for server-side logic (must stay aligned with static/app.js).

Used to decide which notify_box subscribers belong to which box for a season year.
"""
from __future__ import annotations

import re
from datetime import date

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
        "Phish": {
            "A": "Patrick Chifunda",
            "B": "Mark Davis",
            "C": "Josh Wishnack",
            "D": "Scott Harrison",
            "E": "Rene Valdes",
        },
        "Grateful Dead": {
            "A": "John Street",
            "B": "Robert Angle",
            "C": "George Stephenson",
            "D": "Michael Jarvis",
            "E": "Rand Robins",
            "F": "Eddie O'Leary",
        },
        "Widespread Panic": {
            "A": "Manoli Loupassi",
            "B": "Michael Halloran",
            "C": "Andy Mack",
            "D": "Jimmy Meadows",
            "E": "Kijoon Kim",
            "F": "Jon Rasich",
        },
        "String Cheese Incident": {
            "A": "Charles Kempe",
            "B": "Ros Bowers",
            "C": "Jeff Clarke",
            "D": "Jim Davis",
            "E": "Peter Thacker",
            "F": "Shelton Horsley",
        },
        "Goose": {
            "A": "Monty Geho",
            "B": "Sanjay Hinduja",
            "C": "David Shepardson",
            "D": "Tommy Richards",
            "E": "John Patton Jr",
            "F": "Berkeley Edmunds",
        },
        "Umphrey's McGee": {
            "A": "Feizel Bobert",
            "B": "Tom Mitchell",
            "C": "Rick Morris",
            "D": "Matt Chriss",
            "E": "Jimmy Cooke",
            "F": "Mukul Paithane",
        },
        "Disco Biscuits": {
            "A": "Dean King",
            "B": "Spencer Williamson",
            "C": "Frank de Venoge",
            "D": "Teddy Damgard",
            "E": "Alan Burke",
            "F": "Jack Hager",
        },
        "Twiddle": {
            "A": "Robert Gentil",
            "B": "Bob Reynolds",
            "C": "Skylyr Philips",
            "D": "Heidi Stevenson",
            "E": "Nick Farrell",
            "F": "Clark Warthen",
        },
        "Lotus": {
            "A": "Andrew Fois",
            "B": "John Farmer",
            "C": "Chris Dickey",
            "D": "Gaby Hakim",
            "E": "Deesh Bhattal",
            "F": "Robert Huff",
        },
    },
}

# Canonical 15-week box season (must match static/app.js FULL_BOX_MATCHUPS length).
BOX_WEEK_COUNT = 15

# Same order as static/app.js FULL_BOX_MATCHUPS — one date label per week for every box.
FULL_BOX_MATCHUP_DATES: list[str] = [
    "Nov 2–8",
    "Nov 9–15",
    "Nov 16–29",
    "Nov 30–Dec 6",
    "Dec 7–13",
    "Dec 14–27",
    "Dec 28–Jan 3",
    "Jan 4–10",
    "Jan 11–17",
    "Jan 18–24",
    "Jan 25–31",
    "Feb 1–7",
    "Feb 8–14",
    "Feb 15–21",
    "Feb 22–28",
]

# Matchup order for every box tab (must match static/app.js FULL_BOX_MATCHUPS).
FULL_BOX_MATCHUPS: list[str] = [
    "A & D vs B & C",
    "A & F vs D & E",
    "B & E vs C & F",
    "A & B vs D & F",
    "B & E vs C & D",
    "A & C vs D & F",
    "A & E vs B & F",
    "A & B vs C & E",
    "B & D vs C & F",
    "A & E vs C & F",
    "A & C vs B & D",
    "B & D vs E & F",
    "A & D vs C & E",
    "A & F vs B & E",
    "C & E vs D & F",
]

# 2026–2027: biweekly windows starting Aug 30 (6-player: 9 rounds; 5-player: 10).
_BOX_DATES_6_2026 = [
    "Aug 30–Sep 12",
    "Sep 13–Sep 26",
    "Sep 27–Oct 10",
    "Oct 11–Oct 24",
    "Oct 25–Nov 7",
    "Nov 8–Nov 21",
    "Nov 22–Dec 5",
    "self scheduled match",
    "self scheduled match",
]
_BOX_DATES_5_2026 = _BOX_DATES_6_2026 + ["self scheduled match"]

_BOX_MATCHUPS_6_2026 = [
    "A & D vs B & C",
    "A & F vs D & E",
    "B & D vs C & F",
    "A & B vs C & E",
    "B & D vs E & F",
    "A & C vs D & F",
    "A & E vs B & F",
    "B & E vs C & D",
    "A & E vs C & F",
]
_BOX_MATCHUPS_5_2026 = [
    "A & D vs C & E",
    "A & B vs C & D",
    "B & C vs D & E",
    "A & B vs D & E",
    "A & C vs B & E",
    "A & E vs C & D",
    "A & C vs B & D",
    "B & D vs C & E",
    "A & D vs B & E",
    "A & E vs B & C",
]

_JAM_BAND_6_2026 = [
    "Grateful Dead",
    "Widespread Panic",
    "String Cheese Incident",
    "Goose",
    "Umphrey's McGee",
    "Disco Biscuits",
    "Twiddle",
    "Lotus",
]

BOX_SCHEDULE_DATES_BY_YEAR: dict[int, dict[str, list[str]]] = {
    2026: {
        "Phish": list(_BOX_DATES_5_2026),
        **{name: list(_BOX_DATES_6_2026) for name in _JAM_BAND_6_2026},
    },
}

BOX_MATCHUPS_BY_YEAR: dict[int, dict[str, list[str]]] = {
    2026: {
        "Phish": list(_BOX_MATCHUPS_5_2026),
        **{name: list(_BOX_MATCHUPS_6_2026) for name in _JAM_BAND_6_2026},
    },
}

_MONTH_ABBR_BOX = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _calendar_year_for_box_month(month: int, season_year: int) -> int:
    """Fall-start league: Nov–Dec use season_year; Jan–Apr use season_year+1; May–Oct use season_year."""
    if month >= 11:
        return season_year
    if month <= 4:
        return season_year + 1
    return season_year


def parse_box_week_date_span(label: str, season_year: int) -> tuple[date, date] | None:
    """Parse sheet label into inclusive calendar bounds (season_year = UI season start year)."""
    label = label.strip()
    if not label:
        return None
    single = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*$", label)
    if single:
        mon = _MONTH_ABBR_BOX[single.group(1).lower()[:3]]
        day = int(single.group(2))
        y = int(single.group(3))
        try:
            d = date(y, mon, day)
        except ValueError:
            return None
        return d, d

    parts = re.split(r"\s*[–\-]\s*", label, maxsplit=1)
    if len(parts) != 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    lp = left.split()
    if len(lp) < 2:
        return None
    try:
        mon_l = _MONTH_ABBR_BOX[lp[0].lower()[:3]]
        day_l = int(lp[1])
    except (KeyError, ValueError):
        return None
    cy_l = _calendar_year_for_box_month(mon_l, season_year)
    try:
        start = date(cy_l, mon_l, day_l)
    except ValueError:
        return None

    if re.fullmatch(r"\d{1,2}", right):
        try:
            day_r = int(right)
            end = date(cy_l, mon_l, day_r)
        except ValueError:
            return None
    else:
        rp = right.split()
        if len(rp) < 2:
            return None
        try:
            mon_r = _MONTH_ABBR_BOX[rp[0].lower()[:3]]
            day_r = int(rp[1])
        except (KeyError, ValueError):
            return None
        cy_r = _calendar_year_for_box_month(mon_r, season_year)
        try:
            end = date(cy_r, mon_r, day_r)
        except ValueError:
            return None

    if end < start:
        return None
    return start, end


def get_box_week_dates_label(team: str, week: int, season_year: int) -> str | None:
    """Schedule dates cell for this box/week/season (mirrors merged static sheet logic)."""
    if week < 1:
        return None
    y = int(season_year)
    ys = BOX_SCHEDULE_DATES_BY_YEAR.get(y, {}).get(team)
    if ys is not None:
        return ys[week - 1] if week <= len(ys) else None
    if y in BOX_PLAYERS_BY_YEAR:
        return None
    if week <= len(FULL_BOX_MATCHUP_DATES):
        return FULL_BOX_MATCHUP_DATES[week - 1]
    return None


def get_box_matchups(team: str, year: int) -> list[str]:
    """Matchup strings for this box/season (mirrors static/app.js getBoxMatchupsForYear)."""
    y = int(year)
    by_year = BOX_MATCHUPS_BY_YEAR.get(y, {}).get(team)
    if by_year:
        return list(by_year)
    return list(FULL_BOX_MATCHUPS)


def box_week_calendar_contains_date(team: str, week: int, season_year: int, on_date: date) -> bool:
    """True if on_date falls in this box week's schedule window (cron cadence, like handicap week ranges)."""
    lab = get_box_week_dates_label(team, week, season_year)
    if not lab:
        return False
    span = parse_box_week_date_span(lab, season_year)
    if not span:
        return False
    lo, hi = span
    return lo <= on_date <= hi


def box_week_date_bounds(team: str, week: int, season_year: int) -> tuple[date, date] | None:
    """Inclusive start/end dates for this box round."""
    lab = get_box_week_dates_label(team, week, season_year)
    if not lab:
        return None
    return parse_box_week_date_span(lab, season_year)


def box_week_start_date(team: str, week: int, season_year: int) -> date | None:
    """First calendar day of this box round (match reminders send on/after this day at SEND_HOUR ET)."""
    span = box_week_date_bounds(team, week, season_year)
    return span[0] if span else None


def box_week_deadline_date(team: str, week: int, season_year: int) -> date | None:
    """Last calendar day of this box round (standings digest sends at 8 PM ET on this day, if cron runs)."""
    span = box_week_date_bounds(team, week, season_year)
    return span[1] if span else None


def year_uses_explicit_box_list(year: int) -> bool:
    return year in BOX_PLAYERS_BY_YEAR


def get_box_roster_dict(team: str, year: int) -> dict[str, str]:
    """Mirror static/app.js getBoxPlayersForYear (sheet roster); fallback for notification matching."""
    y = int(year)
    if year_uses_explicit_box_list(y):
        explicit = BOX_PLAYERS_BY_YEAR.get(y, {}).get(team)
        if explicit:
            return dict(explicit)
        # Partial year overrides (e.g. only one box tab for 2026): use default sheet for other teams
        # so notify_box subscribers still match canonical names.
        return dict(BOX_PLAYERS.get(team) or {})
    return dict(BOX_PLAYERS.get(team) or {})
