"""
River City Doubles League — Flask backend.
Stores scores in SQLite and serves standings for handicap open/main.
"""
import os
import sqlite3
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                notify_match INTEGER NOT NULL DEFAULT 1,
                notify_round_standings INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        for col, default in (("notify_match", "1"), ("notify_round_standings", "0")):
            try:
                conn.execute(f"ALTER TABLE email_subscriptions ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}")
            except sqlite3.OperationalError:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_notifications_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                level TEXT NOT NULL,
                week INTEGER NOT NULL,
                year INTEGER NOT NULL,
                team1 TEXT NOT NULL,
                team2 TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(email, level, week, year, team1, team2)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS round_standings_notifications_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                level TEXT NOT NULL,
                week INTEGER NOT NULL,
                year INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(email, level, week, year)
            )
        """)
        conn.commit()


def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def split_player_names(value: str):
    """Best-effort parser for player strings like 'A and B', 'A/B', 'A, B'."""
    if not value:
        return []
    cleaned = value.replace("/", ",").replace("&", ",").replace(" and ", ",")
    out = []
    for part in cleaned.split(","):
        n = " ".join(part.strip().split())
        if n:
            out.append(n)
    return out


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def send_match_notification_email(to_email, to_name: str, subject: str, body: str, html_body: str = None):
    """
    Send an email notification.
    Service used: SMTP (intended for SendGrid SMTP in production).
    """
    smtp_host = os.environ.get("RCD_SMTP_HOST", "smtp.sendgrid.net")
    smtp_port = int(os.environ.get("RCD_SMTP_PORT", "587"))
    smtp_user = os.environ.get("RCD_SMTP_USER", "apikey")
    smtp_pass = os.environ.get("RCD_SMTP_PASS", "").strip()
    from_email = os.environ.get("RCD_EMAIL_FROM", "rivercitydoublessquash@gmail.com").strip()
    if not smtp_pass or not from_email:
        # App remains functional even without outbound email configured.
        return False, "Email config missing (RCD_SMTP_PASS and/or RCD_EMAIL_FROM)."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    recipients = to_email if isinstance(to_email, list) else [to_email]
    msg["To"] = ", ".join(recipients)
    greeting = "Hi everyone" if len(recipients) > 1 else f"Hi {to_name}"
    msg.set_content(f"{greeting},\n\n{body}\n\n- River City Doubles")
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


def compute_standings_rows(level, year):
    allowed = [t for t in (TEAMS_OPEN if level == "open" else TEAMS_MAIN) if t not in TEAMS_EXCLUDED]
    teams = {name: {"points": 0, "matches": 0, "wins": 0, "gamesWon": 0} for name in allowed}
    with get_db() as conn:
        rows = conn.execute(
            """SELECT team1, team2, games1, games2 FROM scores
               WHERE league = ? AND level = ? AND (year = ? OR year IS NULL)""",
            ("handicap", level, year),
        ).fetchall()
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
    standings = []
    for name, stats in sorted(teams.items(), key=lambda x: (-x[1]["points"], x[0].lower())):
        losses = stats["matches"] - stats["wins"]
        standings.append({"name": name, **stats, "record": f"{stats['wins']}-{losses}"})
    return standings


def maybe_send_match_play_notifications(level, week, year):
    """
    Notify subscribed players when they are scheduled to play in this week and that
    specific match row still has no score (upcoming/in-progress reminder).
    """
    init_db()
    with get_db() as conn:
        rows = conn.execute(
            """SELECT team1, team2, team1_players, team2_players
               FROM schedule
               WHERE level = ? AND week = ? AND (year = ? OR year IS NULL)
                 AND (score IS NULL OR TRIM(score) = '')""",
            (level, week, year),
        ).fetchall()
        subs = conn.execute(
            """SELECT name, email FROM email_subscriptions
               WHERE is_active = 1 AND notify_match = 1""",
        ).fetchall()
        sent_rows = conn.execute(
            """SELECT email, team1, team2 FROM match_notifications_sent
               WHERE level = ? AND week = ? AND year = ?""",
            (level, week, year),
        ).fetchall()
        sent_keys = {(r["email"], r["team1"], r["team2"]) for r in sent_rows}

    if not rows or not subs:
        return

    sub_by_name = {normalize_name(s["name"]): s for s in subs}
    for row in rows:
        players = split_player_names(row["team1_players"]) + split_player_names(row["team2_players"])
        if not players:
            continue
        players_norm = {normalize_name(p) for p in players}
        recipients = []
        for n_norm in players_norm:
            s = sub_by_name.get(n_norm)
            if not s:
                continue
            key = (s["email"], row["team1"] or "", row["team2"] or "")
            if key in sent_keys:
                continue
            recipients.append(s)
        if not recipients:
            continue
        subject = f"River City Doubles: You are scheduled to play (Week {week})"
        body = (
            f"You are listed in an upcoming {level.title()} handicap match.\n"
            f"Week {week} ({WEEK_DATE_RANGES.get(week, '')}), season {year}-{year + 1}\n"
            f"{row['team1']} vs {row['team2']}\n"
        )
        to_emails = [r["email"] for r in recipients]
        ok, err = send_match_notification_email(to_emails, "players", subject, body)
        if ok:
            with get_db() as conn:
                for r in recipients:
                    conn.execute(
                        """INSERT OR IGNORE INTO match_notifications_sent
                           (email, level, week, year, team1, team2, sent_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (r["email"], level, week, year, row["team1"] or "", row["team2"] or "", now_iso()),
                    )
                conn.commit()
        else:
            print(f"Match notification group email failed ({to_emails}): {err}")


def maybe_send_round_standings_notifications(level, week, year):
    """
    Send standings digest when all non-bye matches in a week have scores.
    """
    init_db()
    with get_db() as conn:
        totals = conn.execute(
            """SELECT
                 SUM(CASE WHEN team1 IS NOT NULL AND team2 IS NOT NULL
                           AND (bye IS NULL OR TRIM(bye) = '') THEN 1 ELSE 0 END) AS expected,
                 SUM(CASE WHEN team1 IS NOT NULL AND team2 IS NOT NULL
                           AND (bye IS NULL OR TRIM(bye) = '')
                           AND score IS NOT NULL AND TRIM(score) <> '' THEN 1 ELSE 0 END) AS completed
               FROM schedule
               WHERE level = ? AND week = ? AND (year = ? OR year IS NULL)""",
            (level, week, year),
        ).fetchone()
        expected = int(totals["expected"] or 0)
        completed = int(totals["completed"] or 0)
        if expected == 0 or completed < expected:
            return

        subs = conn.execute(
            """SELECT name, email FROM email_subscriptions
               WHERE is_active = 1 AND notify_round_standings = 1""",
        ).fetchall()
        sent = conn.execute(
            """SELECT email FROM round_standings_notifications_sent
               WHERE level = ? AND week = ? AND year = ?""",
            (level, week, year),
        ).fetchall()
        sent_emails = {r["email"] for r in sent}

    if not subs:
        return
    standings = compute_standings_rows(level, year)
    lines = []
    for i, row in enumerate(standings, start=1):
        lines.append(
            f"{i}. {row['name']} - {row['points']} pts, {row['record']} record, {row['gamesWon']} games won"
        )
    standings_text = "\n".join(lines) if lines else "No standings yet."
    subject = f"River City Doubles: {level.title()} standings after Week {week}"
    base_body = (
        f"Week {week} is complete for {level.title()} handicap ({year}-{year + 1}).\n\n"
        f"Current standings:\n{standings_text}\n"
    )
    html_rows = "".join(
        (
            "<tr>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{i}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db'>{row['name']}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{row['points']}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{row['matches']}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{row['record']}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{row['gamesWon']}</td>"
            "</tr>"
        )
        for i, row in enumerate(standings, start=1)
    )
    html_body = f"""
<html>
  <body style="font-family:Arial,sans-serif;color:#111827">
    <p>Hi {{{{name}}}},</p>
    <p>Week {week} is complete for {level.title()} handicap ({year}-{year + 1}).</p>
    <p>Current standings:</p>
    <table style='border-collapse:collapse;min-width:680px'>
      <thead>
        <tr style='background:#f3f4f6'>
          <th style='padding:8px;border:1px solid #d1d5db'>#</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Team</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Points</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Matches</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Record</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Games won</th>
        </tr>
      </thead>
      <tbody>
        {html_rows}
      </tbody>
    </table>
    <p style='margin-top:16px'>- River City Doubles</p>
  </body>
</html>
"""
    pending = [s for s in subs if s["email"] not in sent_emails]
    if not pending:
        return
    for s in pending:
        ok, err = send_match_notification_email(
            s["email"],
            s["name"],
            subject,
            base_body,
            html_body=html_body.replace("{name}", s["name"]),
        )
        if ok:
            with get_db() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO round_standings_notifications_sent
                       (email, level, week, year, sent_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (s["email"], level, week, year, now_iso()),
                )
                conn.commit()
        else:
            print(f"Standings email failed for {s['email']}: {err}")


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


@app.route("/api/notifications/subscriptions", methods=["POST"])
def upsert_subscription():
    data = request.get_json() or {}
    name = " ".join((data.get("name") or "").strip().split())
    email = (data.get("email") or "").strip().lower()
    is_active = bool(data.get("is_active", True))
    notify_match = bool(data.get("notify_match", True))
    notify_round_standings = bool(data.get("notify_round_standings", False))
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    init_db()
    ts = now_iso()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM email_subscriptions WHERE email = ?",
            (email,),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE email_subscriptions
                   SET name = ?, is_active = ?, notify_match = ?, notify_round_standings = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    name,
                    1 if is_active else 0,
                    1 if notify_match else 0,
                    1 if notify_round_standings else 0,
                    ts,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """INSERT INTO email_subscriptions
                   (name, email, is_active, notify_match, notify_round_standings, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    email,
                    1 if is_active else 0,
                    1 if notify_match else 0,
                    1 if notify_round_standings else 0,
                    ts,
                    ts,
                ),
            )
        conn.commit()
    return jsonify(
        {
            "ok": True,
            "email": email,
            "is_active": is_active,
            "notify_match": notify_match,
            "notify_round_standings": notify_round_standings,
        }
    ), 200


@app.route("/api/notifications/subscriptions", methods=["DELETE"])
def delete_subscription():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400
    init_db()
    with get_db() as conn:
        conn.execute(
            """UPDATE email_subscriptions
               SET is_active = 0, notify_match = 0, notify_round_standings = 0, updated_at = ?
               WHERE email = ?""",
            (now_iso(), email),
        )
        conn.commit()
    return jsonify({"ok": True, "email": email, "is_active": False}), 200


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
    try:
        maybe_send_match_play_notifications(level, week, year)
        maybe_send_round_standings_notifications(level, week, year)
    except Exception as e:
        print(f"Notification hook failed: {e}")
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
    try:
        year = int((data.get("year") or SEASON_YEARS[-1]))
        maybe_send_match_play_notifications(level, week, year)
    except Exception as e:
        print(f"Schedule notification hook failed: {e}")
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
