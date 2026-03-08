"""
River City Doubles League — Flask backend.
Stores scores in SQLite and serves standings for handicap open/main.
"""
import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(__file__), "scores.db"))

cors_origins = os.environ.get("RCD_CORS_ORIGINS", "*").strip()
CORS(
    app,
    resources={r"/api/*": {"origins": [o.strip() for o in cors_origins.split(",")] if cors_origins != "*" else "*"}},
)


@app.after_request
def no_cache_api(response):
    """Prevent caching of API responses so standings/schedule stay fresh."""
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

TEAMS_OPEN = [
    "Even Older and Grumpier",
    "All the right Angles",
    "El Mustachios",
    "Mack Attack",
    "Old and in the way",
    "Team Nitro",
    "Fatty and Friends",
]
TEAMS_MAIN = [
    "The Double Troubles",
    "The Boast Beasts",
    "Drop Shotz",
    "Tin and Tonic",
]
# Exclude from team lists (e.g. test placeholders)
TEAMS_EXCLUDED = {"A", "B"}

# Open division: team name -> list of player names for that team
TEAM_PLAYERS_OPEN = {
    "Old and in the way": ["Ros Bowers", "Eddie O'Leary", "Monty Geho", "Teddy Damgard"],
    "Even Older and Grumpier": ["Jim Davis", "Sanjay Hinduja", "John Street", "Spencer Williamson", "Jimmy Cooke", "Jim Bonbright"],
    "El Mustachios": ["Mark Davis", "John Street", "Jimmy Cooke", "Tommy Richards"],
    "Fatty and Friends": ["Scott Harrison", "Ned Sinnott", "Grant Stevens", "Matt Chriss"],
    "Mack Attack": ["Andy Mack", "Michael Halloran", "Dave Shepardson", "Jon Rasich"],
    "All the right Angles": ["Robert Angle", "George Stephenson", "Charles Kempe", "Jimmy Meadows"],
    "Team Nitro": ["Josh Wishnack", "Manoli Loupassi", "Berkeley Edmunds", "Frank Devenoge", "Dean King"],
}

# Main division: no roster provided, so all players available (we could add TEAM_PLAYERS_MAIN later)
TEAM_PLAYERS_MAIN = {}

PLAYERS = [
    "Ros Bowers",
    "Jim Davis",
    "Mark Davis",
    "Josh Wishnack",
    "Eddie O'Leary",
    "Sanjay Hinduja",
    "John Street",
    "Manoli Loupassi",
    "Monty Geho",
    "Spencer Williamson",
    "Jimmy Cooke",
    "Berkeley Edmunds",
    "Teddy Damgard",
    "Jim Bonbright",
    "Tommy Richards",
    "Frank Devenoge",
    "Dean King",
    "Scott Harrison",
    "Andy Mack",
    "Robert Angle",
    "Ned Sinnott",
    "Michael Halloran",
    "George Stephenson",
    "Grant Stevens",
    "Dave Shepardson",
    "Charles Kempe",
    "Matt Chriss",
    "Jon Rasich",
    "Jimmy Meadows",
]

WEEK_DATE_RANGES = {
    1: "Jan 18–Jan 24",
    2: "Jan 25–Jan 31",
    3: "Feb 1–Feb 7",
    4: "Feb 8–Feb 14",
    5: "Feb 15–Feb 21",
    6: "Feb 22–Feb 28",
    7: "Mar 1–Mar 7",
}

# Single active season; exposed via /api/years
SEASON_YEARS = [2025]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT NOT NULL,
                level TEXT NOT NULL,
                week INTEGER NOT NULL,
                handicap TEXT,
                team1 TEXT NOT NULL,
                team2 TEXT NOT NULL,
                games1 INTEGER NOT NULL,
                games2 INTEGER NOT NULL,
                team1_players TEXT,
                team2_players TEXT,
                year INTEGER
            )
        """)
        for col in ("team1_players", "team2_players"):
            try:
                conn.execute(f"ALTER TABLE scores ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE scores ADD COLUMN year INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                week INTEGER NOT NULL,
                date_range TEXT,
                team1 TEXT,
                team2 TEXT,
                bye TEXT,
                team1_players TEXT,
                team2_players TEXT,
                handicap TEXT,
                score TEXT,
                winner TEXT,
                year INTEGER
            )
        """)
        try:
            conn.execute("ALTER TABLE schedule ADD COLUMN year INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def ensure_db_ready():
    """Create/upgrade tables if needed (safe to call repeatedly)."""
    init_db()
    seed_if_empty()


def seed_if_empty():
    """
    One-time seed of 2025 handicap Open/Main schedule + scores if the DB is empty.
    Uses the existing seed scripts so local + Render stay in sync.
    """
    try:
        with get_db() as conn:
            # If we already have any 2025 schedule rows, assume it has been seeded.
            existing = conn.execute(
                "SELECT COUNT(*) AS c FROM schedule WHERE year = ?",
                (2025,),
            ).fetchone()
            if existing and existing["c"] > 0:
                return
    except sqlite3.Error:
        # If we can't even query schedule, let the API path surface the error.
        return

    try:
        # Import only when needed to avoid unnecessary work on every request.
        import seed_schedule
        import seed_main_schedule
        import backfill_standings_from_schedule

        seed_schedule.main()
        seed_main_schedule.main()
        backfill_standings_from_schedule.main()
    except Exception:
        # If seeding fails (e.g. read-only FS), leave DB empty and let API calls
        # behave as "no data yet" or surface DB errors for debugging.
        return


def points_for_team(games_won: int, is_winner: bool) -> int:
    """1 pt play, 1 pt win, 1 pt per game won."""
    pts = 1
    if is_winner:
        pts += 1
    return pts + games_won


@app.route("/health")
def health():
    """Lightweight endpoint for Render health checks and keep-alive pings (e.g. UptimeRobot every 5–10 min to avoid free-tier spin-down)."""
    return jsonify({"status": "ok"}), 200


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/main_division_handicap_2025.JPG")
def main_division_image():
    path = os.path.join(STATIC_DIR, "main_division_handicap_2025.JPG")
    return send_file(path, mimetype="image/jpeg")


@app.route("/open_division_handicap_2025.JPG")
def open_division_image():
    path = os.path.join(STATIC_DIR, "open_division_handicap_2025.JPG")
    return send_file(path, mimetype="image/jpeg")


@app.route("/manifest.webmanifest")
def serve_manifest():
    path = os.path.join(STATIC_DIR, "manifest.webmanifest")
    return send_file(path, mimetype="application/manifest+json")


@app.route("/api/players")
def get_players():
    return jsonify(PLAYERS)


@app.route("/api/team-players/<level>")
def get_team_players(level):
    """Return { team_name: [player1, player2, ...] } for the given level (open/main)."""
    if level not in ("open", "main"):
        return jsonify({"error": "level must be open or main"}), 400
    rosters = TEAM_PLAYERS_OPEN if level == "open" else TEAM_PLAYERS_MAIN
    return jsonify(rosters)


@app.route("/api/weeks")
def get_weeks():
    """Week number and date range for the Input Score form."""
    return jsonify([{"week": w, "date_range": WEEK_DATE_RANGES[w]} for w in sorted(WEEK_DATE_RANGES)])


@app.route("/api/years")
def get_years():
    """Season years for the year dropdown."""
    return jsonify(SEASON_YEARS)


def _normalize_team_order(level, week, year, team1, team2, games1, games2, team1_players, team2_players, h1, h2):
    """
    Normalize (team1, team2) and corresponding fields so order doesn't matter when inputting.
    Prefer schedule order if a schedule row exists; otherwise use alphabetical team order.
    Returns (team1, team2, games1, games2, team1_players, team2_players, h1, h2).
    """
    with get_db() as conn:
        sched = conn.execute(
            """SELECT team1, team2 FROM schedule
               WHERE level = ? AND week = ? AND (year = ? OR (year IS NULL AND ? IS NULL))
                 AND ((team1 = ? AND team2 = ?) OR (team1 = ? AND team2 = ?))""",
            (level, week, year, year, team1, team2, team2, team1),
        ).fetchone()
    if sched:
        canon1, canon2 = sched["team1"], sched["team2"]
        if (team1, team2) == (canon2, canon1):
            return (canon1, canon2, games2, games1, team2_players, team1_players, h2, h1)
        return (canon1, canon2, games1, games2, team1_players, team2_players, h1, h2)
    # No schedule row: use alphabetical order so the same match is always stored the same way
    t1, t2 = sorted([team1, team2])
    if (team1, team2) == (t2, t1):
        return (t1, t2, games2, games1, team2_players, team1_players, h2, h1)
    return (t1, t2, games1, games2, team1_players, team2_players, h1, h2)


@app.route("/api/scores", methods=["POST"])
def post_score():
    data = request.get_json() or {}
    league = (data.get("league") or "").strip().lower()
    level = (data.get("level") or "").strip().lower()
    week = data.get("week")
    team1 = (data.get("team1") or "").strip()
    team2 = (data.get("team2") or "").strip()
    games1 = int(data.get("games1", 0))
    games2 = int(data.get("games2", 0))
    h1 = (data.get("handicap_team1") or "").strip() or None
    h2 = (data.get("handicap_team2") or "").strip() or None
    team1_players = (data.get("team1_players") or "").strip() or None
    team2_players = (data.get("team2_players") or "").strip() or None
    year = data.get("year")
    if year is not None:
        year = int(year) if isinstance(year, int) else int(year) if str(year).strip() else None
    if year is None:
        year = SEASON_YEARS[-1]  # default to most recent

    if league not in ("box", "handicap") or level not in ("open", "main"):
        return jsonify({"error": "Invalid league or level"}), 400
    allowed = [t for t in (TEAMS_OPEN if level == "open" else TEAMS_MAIN) if t not in TEAMS_EXCLUDED]
    if team1 not in allowed or team2 not in allowed:
        return jsonify({"error": "Invalid team name for this level"}), 400
    if team1 == team2:
        return jsonify({"error": "Team 1 and Team 2 must be different"}), 400
    if not isinstance(week, int) or week < 1:
        return jsonify({"error": "Week must be a positive integer"}), 400
    if not (0 <= games1 <= 3 and 0 <= games2 <= 3):
        return jsonify({"error": "No team can win more than 3 games"}), 400
    if games1 + games2 > 5:
        return jsonify({"error": "Best of 5: total games cannot exceed 5"}), 400

    # Normalize so order of teams (and thus players/handicaps) doesn't matter
    if level in ("open", "main"):
        team1, team2, games1, games2, team1_players, team2_players, h1, h2 = _normalize_team_order(
            level, week, year, team1, team2, games1, games2, team1_players, team2_players, h1, h2
        )
    handicap = " / ".join(p for p in (h1, h2) if p) or None
    score_str = f"{games1}-{games2}"
    winner = team1 if games1 > games2 else (team2 if games2 > games1 else None)

    with get_db() as conn:
        # Upsert score: update if same match (either order) already exists for this week
        existing = conn.execute(
            """SELECT id, team1, team2 FROM scores
               WHERE league = ? AND level = ? AND week = ? AND (year = ? OR (year IS NULL AND ? IS NULL))
                 AND ((team1 = ? AND team2 = ?) OR (team1 = ? AND team2 = ?))""",
            (league, level, week, year, year, team1, team2, team2, team1),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE scores SET handicap = ?, team1 = ?, team2 = ?, games1 = ?, games2 = ?,
                   team1_players = ?, team2_players = ?, year = ?
                   WHERE id = ?""",
                (handicap, team1, team2, games1, games2, team1_players, team2_players, year, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO scores (league, level, week, handicap, team1, team2, games1, games2, team1_players, team2_players, year)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (league, level, week, handicap, team1, team2, games1, games2, team1_players, team2_players, year),
            )
        conn.commit()
        # Upsert schedule row for this match so spreadsheet shows players, score, winner
        if level in ("open", "main"):
            existing_sched = conn.execute(
                """SELECT id FROM schedule WHERE level = ? AND week = ? AND ((team1 = ? AND team2 = ?) OR (team1 = ? AND team2 = ?)) AND (year = ? OR (year IS NULL AND ? IS NULL))""",
                (level, week, team1, team2, team2, team1, year, year),
            ).fetchone()
            date_range = WEEK_DATE_RANGES.get(week, "")
            if existing_sched:
                conn.execute(
                    """UPDATE schedule SET date_range = ?, team1 = ?, team2 = ?, team1_players = ?, team2_players = ?, handicap = ?, score = ?, winner = ?, year = ?
                       WHERE id = ?""",
                    (date_range, team1, team2, team1_players, team2_players, handicap, score_str, winner, year, existing_sched["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO schedule (level, week, date_range, team1, team2, team1_players, team2_players, handicap, score, winner, year)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (level, week, date_range, team1, team2, team1_players, team2_players, handicap, score_str, winner, year),
                )
            conn.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/standings/<league>/<level>")
def get_standings(league, level):
    if league != "handicap" or level not in ("open", "main"):
        return jsonify({"error": "Only handicap open/main standings supported"}), 400
    year = request.args.get("year", type=int)
    if year is None:
        year = SEASON_YEARS[-1]

    allowed = [t for t in (TEAMS_OPEN if level == "open" else TEAMS_MAIN) if t not in TEAMS_EXCLUDED]
    teams = {name: {"points": 0, "matches": 0, "wins": 0, "gamesWon": 0} for name in allowed}

    try:
        ensure_db_ready()
        with get_db() as conn:
            rows = conn.execute(
                """SELECT team1, team2, games1, games2 FROM scores
                   WHERE league = ? AND level = ? AND (year = ? OR year IS NULL)""",
                (league, level, year),
            ).fetchall()
    except sqlite3.Error as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500

    for r in rows:
        t1, t2 = r["team1"], r["team2"]
        g1, g2 = int(r["games1"]), int(r["games2"])
        winner = 1 if g1 > g2 else (2 if g2 > g1 else None)
        for name, games, is_win in [(t1, g1, winner == 1), (t2, g2, winner == 2)]:
            if name in teams:
                teams[name]["points"] += points_for_team(games, is_win)
                teams[name]["matches"] += 1
                teams[name]["wins"] += 1 if is_win else 0
                teams[name]["gamesWon"] += games

    # Rank by points (desc); use alphabetical order only when points are equal
    standings = []
    for name, stats in sorted(teams.items(), key=lambda x: (-x[1]["points"], x[0].lower())):
        losses = stats["matches"] - stats["wins"]
        standings.append({"name": name, **stats, "record": f"{stats['wins']}-{losses}"})
    return jsonify(standings)


@app.route("/api/schedule")
def get_schedule():
    level = request.args.get("level", "").strip().lower()
    if level not in ("open", "main"):
        return jsonify({"error": "level must be open or main"}), 400
    year = request.args.get("year", type=int)
    if year is None:
        year = SEASON_YEARS[-1]
    try:
        ensure_db_ready()
        with get_db() as conn:
            rows = conn.execute(
                """SELECT id, week, date_range, team1, team2, bye, team1_players, team2_players,
                          handicap, score, winner FROM schedule WHERE level = ? AND (year = ? OR year IS NULL) ORDER BY week, id""",
                (level, year),
            ).fetchall()
    except sqlite3.Error as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500
    # Deduplicate: same (week, team pair) can appear twice; prefer the row that has a score
    by_key = {}
    for r in rows:
        key = (r["week"], tuple(sorted([(r["team1"] or ""), (r["team2"] or "")])))
        row_data = {
            "week": r["week"],
            "date_range": (r["date_range"] or "").strip() or WEEK_DATE_RANGES.get(r["week"], ""),
            "team1": r["team1"] or "",
            "team2": r["team2"] or "",
            "bye": r["bye"] or "",
            "team1_players": r["team1_players"] or "",
            "team2_players": r["team2_players"] or "",
            "handicap": r["handicap"] or "",
            "score": r["score"] or "",
            "winner": r["winner"] or "",
        }
        existing = by_key.get(key)
        if existing is None or (row_data["score"] and not existing["score"]):
            by_key[key] = row_data
    out = list(by_key.values())
    out.sort(key=lambda x: (x["week"], x["team1"], x["team2"]))
    return jsonify(out)


@app.route("/api/schedule", methods=["POST"])
def post_schedule():
    data = request.get_json() or {}
    level = (data.get("level") or "").strip().lower()
    week = data.get("week")
    if level not in ("open", "main"):
        return jsonify({"error": "level must be open or main"}), 400
    if not isinstance(week, int) or week < 1:
        return jsonify({"error": "week must be a positive integer"}), 400
    with get_db() as conn:
        conn.execute(
            """INSERT INTO schedule (level, week, date_range, team1, team2, bye, team1_players, team2_players, handicap, score, winner)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                level,
                week,
                (data.get("date_range") or "").strip() or None,
                (data.get("team1") or "").strip() or None,
                (data.get("team2") or "").strip() or None,
                (data.get("bye") or "").strip() or None,
                (data.get("team1_players") or "").strip() or None,
                (data.get("team2_players") or "").strip() or None,
                (data.get("handicap") or "").strip() or None,
                (data.get("score") or "").strip() or None,
                (data.get("winner") or "").strip() or None,
            ),
        )
        conn.commit()
    return jsonify({"ok": True}), 201


if __name__ == "__main__":
    init_db()
    try:
        with get_db() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM scores WHERE league = ? AND level IN ('open', 'main')",
                ("handicap",),
            ).fetchone()[0]
        print(f"Using database: {DB_PATH} ({n} handicap scores)")
    except Exception as e:
        print(f"Using database: {DB_PATH} (check failed: {e})")
    app.run(debug=True, port=5000)
