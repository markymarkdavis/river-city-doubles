"""
River City Doubles League — Flask backend.
Stores scores in SQLite and serves standings for handicap open/main.
"""
import json
import logging
import os
import re
import smtplib
import sqlite3
import ssl
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from email.utils import formataddr, parseaddr

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify, send_from_directory, send_file, Response
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from box_rosters import (
    FULL_BOX_MATCHUPS,
    box_week_date_bounds,
    box_week_deadline_date,
    box_week_start_date,
    get_box_roster_dict,
    get_box_week_dates_label,
)
from rcd_db import DB_PATH, get_db, use_turso

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
log = logging.getLogger("rcd")
ASSET_VERSION = os.environ.get("RCD_ASSET_VERSION", datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
# Optional: change this on Render (e.g. bump "2") to force every browser to reload once and drop SW + caches.
CLIENT_RELOAD_BUMP = os.environ.get("RCD_CLIENT_RELOAD_BUMP", "").strip()

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


@app.errorhandler(Exception)
def api_unhandled_exception(e):
    """Return JSON for API errors (avoids generic HTML 500 from the WSGI server)."""
    if isinstance(e, HTTPException):
        return e
    if request.path.startswith("/api/"):
        log.exception("Unhandled API error on %s", request.path)
        return jsonify({"ok": False, "error": str(e)}), 500
    raise

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

# Box league tab names (must match static/app.js BOX_PLAYERS keys).
BOX_TEAM_NAMES = frozenset(
    {
        "Foo Fighters",
        "Pink Floyd",
        "Dire Straits",
        "Metallica",
        "Nirvana",
        "Fleetwood Mac",
        "Guns N' Roses",
        "Pearl Jam",
        "Deep Purple",
    }
)

# Open division: team name -> list of player names for that team
TEAM_PLAYERS_OPEN = {
    "Old and in the way": ["Ros Bowers", "Eddie O'Leary", "Monty Geho", "Teddy Damgard"],
    "Even Older and Grumpier": ["Jim Davis", "Sanjay Hinduja", "John Street", "Spencer Williamson", "Jimmy Cooke", "Jim Bonbright"],
    "El Mustachios": ["Mark Davis", "John Street", "Jimmy Cooke", "Tommy Richards"],
    "Fatty and Friends": ["Scott Harrison", "Ned Sinnott", "Grant Stevens", "Matt Chriss"],
    "Mack Attack": ["Andy Mack", "Michael Halloran", "David Shepardson", "Jon Rasich"],
    "All the right Angles": ["Robert Angle", "George Stephenson", "Charles Kempe", "Jimmy Meadows"],
    "Team Nitro": ["Josh Wishnack", "Manoli Loupassi", "Berkeley Edmunds", "Frank De Venoge", "Dean King"],
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
    "Frank De Venoge",
    "Dean King",
    "Scott Harrison",
    "Andy Mack",
    "Robert Angle",
    "Ned Sinnott",
    "Michael Halloran",
    "George Stephenson",
    "Grant Stevens",
    "David Shepardson",
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

_MONTH_ABBR = {
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

# Seasons shown in the year dropdown; exposed via /api/years
SEASON_YEARS = [2025, 2026]
# When a request omits year, keep 2025–2026 as the default handicap season
DEFAULT_SEASON_YEAR = 2025

# libsql (Turso) raises ValueError for many SQL errors; sqlite3 uses OperationalError.
_SCHEMA_ERRORS = (sqlite3.OperationalError, ValueError)
_DB_API_ERRORS = (sqlite3.Error, ValueError)


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
            except _SCHEMA_ERRORS:
                pass
        try:
            conn.execute("ALTER TABLE scores ADD COLUMN year INTEGER")
        except _SCHEMA_ERRORS:
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
        except _SCHEMA_ERRORS:
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
            except _SCHEMA_ERRORS:
                pass
        for col, default in (("notify_handicap", "0"), ("notify_box", "0")):
            try:
                conn.execute(f"ALTER TABLE email_subscriptions ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}")
            except _SCHEMA_ERRORS:
                pass
        # One-time backfill: legacy match/standings flags → handicap league bucket.
        try:
            conn.execute(
                """UPDATE email_subscriptions SET notify_handicap = 1
                   WHERE (notify_match = 1 OR notify_round_standings = 1) AND notify_handicap = 0"""
            )
        except _SCHEMA_ERRORS:
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS box_score_notifications_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                level TEXT NOT NULL,
                week INTEGER NOT NULL,
                year INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(email, level, week, year)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS box_match_reminders_sent (
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


def notification_today() -> date:
    """Calendar date used for daily cron (default US Eastern)."""
    return notification_now_et().date()


def notification_now_et() -> datetime:
    """Current local time for notification scheduling (default America/New_York)."""
    tz_name = os.environ.get("RCD_NOTIFICATION_TZ", "America/New_York").strip() or "America/New_York"
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        log.warning("Timezone %r unavailable; using UTC-5 for notification datetime", tz_name)
        eastern = timezone(timedelta(hours=-5))
        return datetime.now(eastern)


def notification_send_hour_et() -> int:
    """Hour (0–23) when first-morning match reminders may first send on the round's start day."""
    raw = os.environ.get("RCD_NOTIFICATION_SEND_HOUR_ET", "8").strip()
    try:
        h = int(raw)
    except ValueError:
        return 8
    return max(0, min(23, h))


def notification_standings_send_hour_et() -> int:
    """Hour (0–23) when standings digests may first send on the round's last calendar day (default 20 = 8 PM)."""
    raw = os.environ.get("RCD_NOTIFICATION_STANDINGS_SEND_HOUR_ET", "20").strip()
    try:
        h = int(raw)
    except ValueError:
        return 20
    return max(0, min(23, h))


def notification_delivery_allowed_on_or_after_anchor(
    anchor_day: date, now_et: datetime, *, send_hour: int | None = None
) -> bool:
    """Eligible on anchor_day at send_hour or later; on later days, any time (catch-up if cron missed anchor day)."""
    hour = notification_send_hour_et() if send_hour is None else send_hour
    today = now_et.date()
    if today < anchor_day:
        return False
    if today > anchor_day:
        return True
    return now_et.hour >= hour


def notification_delivery_allowed_after_deadline(deadline: date, now_et: datetime) -> bool:
    """Eligible on deadline day at standings send hour (default 8 PM ET) or later; after deadline, any time (catch-up)."""
    return notification_delivery_allowed_on_or_after_anchor(
        deadline, now_et, send_hour=notification_standings_send_hour_et()
    )


def _parse_month_day_token(token: str) -> tuple[int, int]:
    parts = token.strip().split()
    if len(parts) < 2:
        raise ValueError(f"invalid date token: {token!r}")
    month = _MONTH_ABBR[parts[0].lower()[:3]]
    day = int(parts[1])
    return month, day


def handicap_week_date_bounds(week: int, season_year: int) -> tuple[date, date]:
    """Inclusive start/end dates for a handicap week in a season year."""
    date_range = WEEK_DATE_RANGES.get(week)
    if not date_range:
        raise ValueError(f"unknown week: {week}")
    left, right = (p.strip() for p in re.split(r"[–\-]", date_range, maxsplit=1))
    m1, d1 = _parse_month_day_token(left)
    m2, d2 = _parse_month_day_token(right)
    start = date(season_year, m1, d1)
    end = date(season_year, m2, d2)
    if end < start:
        end = date(season_year + 1, m2, d2)
    return start, end


def handicap_season_year_for_date(on_date: date) -> int | None:
    """Season year if on_date falls within that season's handicap weeks."""
    for year in sorted(SEASON_YEARS, reverse=True):
        try:
            season_start, _ = handicap_week_date_bounds(1, year)
            _, season_end = handicap_week_date_bounds(max(WEEK_DATE_RANGES), year)
        except ValueError:
            continue
        if season_start <= on_date <= season_end:
            return year
    return None


def handicap_week_for_date(on_date: date, season_year: int) -> int | None:
    for week in sorted(WEEK_DATE_RANGES):
        start, end = handicap_week_date_bounds(week, season_year)
        if start <= on_date <= end:
            return week
    return None


def handicap_week_contains_date(week: int, season_year: int, on_date: date) -> bool:
    start, end = handicap_week_date_bounds(week, season_year)
    return start <= on_date <= end


def notification_weeks_for_date(on_date: date, season_year: int) -> dict:
    """
    Weeks to evaluate on a daily cron for on_date.
    match_week: handicap week containing on_date (reminders send on/after that week's first morning).
    standings_weeks: handicap weeks whose round ended on or before on_date (digests send only after
    week's last calendar day reaches STANDINGS_SEND_HOUR_ET (default 8 PM) — see maybe_send_round_standings_notifications).
    """
    match_week = handicap_week_for_date(on_date, season_year)
    standings_weeks: list[int] = []
    for week in sorted(WEEK_DATE_RANGES):
        _, end = handicap_week_date_bounds(week, season_year)
        if end <= on_date:
            standings_weeks.append(week)
    return {"match_week": match_week, "standings_weeks": standings_weeks}


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


def players_for_schedule_match(level: str, team1: str, team2: str, team1_players: str, team2_players: str) -> list:
    """Player names for a schedule row; falls back to static team rosters when schedule fields are empty."""
    players = split_player_names(team1_players) + split_player_names(team2_players)
    if players:
        return players
    rosters = TEAM_PLAYERS_OPEN if level == "open" else TEAM_PLAYERS_MAIN
    for team in (team1 or "", team2 or ""):
        team = team.strip()
        if team and team in rosters:
            players.extend(rosters[team])
    return players


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _outbound_from_email():
    """Verified From address; defaults to legacy Gmail if unset (SMTP setups)."""
    raw = os.environ.get("RCD_EMAIL_FROM", "").strip()
    return raw or "rivercitydoublessquash@gmail.com"


def _smtp_from_addresses(from_email: str) -> tuple[str, str]:
    """
    Return (From header value, envelope MAIL FROM).
    Brevo/SendGrid require the envelope sender to match a verified address.
    RCD_EMAIL_FROM may be 'Name <email@domain.com>' or bare email.
    """
    display_default = os.environ.get("RCD_EMAIL_FROM_NAME", "River City Doubles").strip() or "River City Doubles"
    name, addr = parseaddr(from_email)
    if not addr:
        addr = from_email.strip()
    if not addr or "@" not in addr:
        raise ValueError(
            "RCD_EMAIL_FROM must be a verified sender email (optionally 'Name <you@domain.com>')."
        )
    if not name:
        name = display_default
    return formataddr((name, addr)), addr


def _email_transport_configured():
    """True if any outbound email transport is configured."""
    if os.environ.get("RCD_RESEND_API_KEY", "").strip():
        return True
    if os.environ.get("RCD_BREVO_API_KEY", "").strip():
        return True
    return bool(os.environ.get("RCD_SMTP_PASS", "").strip())


def _send_resend(api_key, from_email, recipients, subject, text_content, html_body):
    payload = {"from": from_email, "to": recipients, "subject": subject, "text": text_content}
    if html_body:
        payload["html"] = html_body
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("RCD_RESEND_TIMEOUT", "30"))) as resp:
            resp.read()
        log.info("Resend email sent: subject=%r to=%s", subject, len(recipients))
        return True, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(err_body).get("message", err_body)
        except json.JSONDecodeError:
            msg = err_body or str(e)
        log.warning("Resend API failed: %s", msg)
        return False, msg
    except Exception as e:
        log.warning("Resend send failed: %s", e)
        return False, str(e)


def _send_brevo_api(api_key, from_email, recipients, subject, text_content, html_body=None):
    """Brevo transactional email over HTTPS (preferred on Render when SMTP times out)."""
    try:
        from_header, envelope_from = _smtp_from_addresses(from_email)
    except ValueError as e:
        return False, str(e)
    name, _addr = parseaddr(from_header)
    if not name:
        name = os.environ.get("RCD_EMAIL_FROM_NAME", "River City Doubles").strip() or "River City Doubles"
    payload = {
        "sender": {"name": name, "email": envelope_from},
        "to": [{"email": r} for r in recipients],
        "subject": subject,
        "textContent": text_content,
    }
    if html_body:
        payload["htmlContent"] = html_body
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=data,
        method="POST",
        headers={"api-key": api_key, "Content-Type": "application/json", "accept": "application/json"},
    )
    try:
        timeout = int(os.environ.get("RCD_BREVO_API_TIMEOUT", "30"))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        log.info("Brevo API email sent: subject=%r to=%s", subject, recipients)
        return True, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body)
            msg = parsed.get("message") or parsed.get("code") or err_body
        except json.JSONDecodeError:
            msg = err_body or str(e)
        log.warning("Brevo API failed: %s", msg)
        return False, msg
    except Exception as e:
        log.warning("Brevo API send failed: %s", e)
        return False, str(e)


def _send_smtp(from_email, recipients, subject, text_content, html_body):
    smtp_host = os.environ.get("RCD_SMTP_HOST", "smtp.sendgrid.net").strip()
    smtp_port = int(os.environ.get("RCD_SMTP_PORT", "587"))
    smtp_user = os.environ.get("RCD_SMTP_USER", "apikey").strip()
    smtp_pass = os.environ.get("RCD_SMTP_PASS", "").strip()
    use_ssl = os.environ.get("RCD_SMTP_SSL", "").strip().lower() in ("1", "true", "yes")
    # Stay under Gunicorn's default 30s worker timeout so Flask can return JSON errors.
    timeout = int(os.environ.get("RCD_SMTP_TIMEOUT", "25"))

    if not smtp_pass:
        return False, "RCD_SMTP_PASS is not set"
    if not smtp_user:
        return False, "RCD_SMTP_USER is not set (for Brevo, use your Brevo login email)"

    try:
        from_header, envelope_from = _smtp_from_addresses(from_email)
    except ValueError as e:
        return False, str(e)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_content)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    ctx = ssl.create_default_context()
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout, context=ctx) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(envelope_from, recipients, msg.as_bytes(policy=SMTP_POLICY))
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(envelope_from, recipients, msg.as_bytes(policy=SMTP_POLICY))
        log.info(
            "SMTP email sent: subject=%r from=%s to=%s via %s:%s",
            subject,
            envelope_from,
            recipients,
            smtp_host,
            smtp_port,
        )
        return True, None
    except Exception as e:
        log.warning("Email send failed (%s:%s ssl=%s from=%s): %s", smtp_host, smtp_port, use_ssl, envelope_from, e)
        return False, str(e)


def send_match_notification_email(to_email, to_name: str, subject: str, body: str, html_body: str = None):
    """
    Send notification email via Resend (HTTP) or SMTP.

    Configure one of:
      • RCD_RESEND_API_KEY — Resend (https://resend.com); set RCD_EMAIL_FROM to a verified sender.
      • RCD_BREVO_API_KEY — Brevo HTTP API (recommended on Render; get key under SMTP & API → API keys).
      • RCD_SMTP_PASS — SMTP (Brevo relay, etc.); optional RCD_EMAIL_FROM (defaults if unset).

    Optional SMTP: RCD_SMTP_HOST, RCD_SMTP_PORT (default 587), RCD_SMTP_USER (default apikey),
    RCD_SMTP_SSL=1 for implicit TLS (e.g. port 465).
    """
    from_email = _outbound_from_email()
    resend_key = os.environ.get("RCD_RESEND_API_KEY", "").strip()
    brevo_key = os.environ.get("RCD_BREVO_API_KEY", "").strip()
    smtp_pass = os.environ.get("RCD_SMTP_PASS", "").strip()

    if not resend_key and not brevo_key and not smtp_pass:
        log.warning("Email skipped: set RCD_RESEND_API_KEY, RCD_BREVO_API_KEY, or RCD_SMTP_PASS.")
        return False, "Email config missing (RCD_BREVO_API_KEY or RCD_SMTP_PASS recommended)."

    recipients = to_email if isinstance(to_email, list) else [to_email]
    greeting = "Hi everyone" if len(recipients) > 1 else f"Hi {to_name}"
    text_content = f"{greeting},\n\n{body}\n\n- River City Doubles"

    if resend_key:
        return _send_resend(resend_key, from_email, recipients, subject, text_content, html_body)
    if brevo_key:
        return _send_brevo_api(brevo_key, from_email, recipients, subject, text_content, html_body)
    return _send_smtp(from_email, recipients, subject, text_content, html_body)


def maybe_send_subscription_welcome(email: str, name: str, notify_handicap: bool, notify_box: bool):
    """Best-effort confirmation after a new subscription row is created."""
    if not (notify_handicap or notify_box):
        return False, None
    if not _email_transport_configured():
        return False, None
    topics = []
    if notify_handicap:
        topics.append(
            "Handicap league — a reminder on the first morning of each week you're scheduled to play "
            "(US Eastern), and standings after each week once all matches are in (evening of the last day of that week)."
        )
    if notify_box:
        topics.append(
            "Box league — a reminder on the first morning of each box round you're on the roster for, "
            "plus a season standings snapshot on the evening of the last day of each round. "
            "Your name must match the box roster for that season."
        )
    lines = "\n".join(f"• {t}" for t in topics)
    body = (
        "You're signed up for River City Doubles email updates.\n\n"
        f"We may send:\n{lines}\n\n"
        "If you didn't request this, you can ignore this message or use Remove my email on the site.\n"
    )
    display_name = name.strip() if name else "there"
    return send_match_notification_email(
        email,
        display_name,
        "River City Doubles: You're subscribed",
        body,
    )


def send_example_notification_email(to_email: str, to_name: str = "there"):
    """Send a sample message showing handicap + box notification styles (for testing)."""
    name = (to_name or "there").strip() or "there"
    subject = "River City Doubles: Example notification email"
    body = (
        "This is an example of the kinds of emails you may receive after signing up on the site.\n\n"
        "—— Handicap league (when you opt in) ——\n"
        "Match reminder example (first morning of the week, US Eastern):\n"
        "  You are listed in an upcoming Open handicap match.\n"
        "  Week 3 (Feb 1–Feb 7), season 2025-2026\n"
        "  Fatty and Friends vs Team Nitro\n\n"
        "Standings example (after all matches in a week are scored for your division):\n"
        "  Sent on or after 8 PM US Eastern on the last day of that week, not immediately when the last score is posted.\n"
        "  Week 3 is complete for Open handicap (2025-2026).\n"
        "  Current standings: team list and points for Open only.\n\n"
        "—— Box league (only if you check Box league on the form) ——\n"
        "  First-morning reminder for your box round with the week's matchup.\n"
        "  Season standings for your box (games won per player) after each round ends.\n"
        "  We only send these if your first and last name matches that box roster.\n\n"
        "Use the same first and last name spelling as on the schedule or box sheet when you subscribe.\n"
    )
    return send_match_notification_email(to_email, name, subject, body)


def _notification_admin_secret_ok(supplied: str) -> bool:
    """Accept cron or test secret for admin-only notification endpoints."""
    supplied = (supplied or "").strip()
    if not supplied:
        return False
    for key in ("RCD_CRON_SECRET", "RCD_NOTIFICATION_TEST_SECRET"):
        expected = os.environ.get(key, "").strip()
        if expected and supplied == expected:
            return True
    return False


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


_BOX_MATCHUP_RE = re.compile(r"^([A-F]) & ([A-F]) vs ([A-F]) & ([A-F])$")


def _parse_box_matchup_sides(matchup: str) -> tuple[list[str], list[str]]:
    m = _BOX_MATCHUP_RE.match((matchup or "").strip())
    if not m:
        return [], []
    return [m.group(1), m.group(2)], [m.group(3), m.group(4)]


def _side_label_to_two_letters(label: str) -> frozenset[str] | None:
    if not label or not str(label).strip():
        return None
    letters: list[str] = []
    for token in re.split(r"\s*&\s*", str(label).strip()):
        t = token.strip().upper()
        if len(t) == 1 and "A" <= t <= "F":
            letters.append(t)
        else:
            return None
    if len(letters) != 2:
        return None
    return frozenset(letters)


def box_week_matchup_player_names(box_team: str, week: int, year: int) -> tuple[str, list[str], list[str]]:
    """(matchup label, side1 display names, side2 display names) for this box week."""
    if week < 1 or week > len(FULL_BOX_MATCHUPS):
        return "", [], []
    matchup = FULL_BOX_MATCHUPS[week - 1]
    roster = get_box_roster_dict(box_team, year)
    letters1, letters2 = _parse_box_matchup_sides(matchup)
    if len(letters1) != 2 or len(letters2) != 2:
        return matchup, [], []

    def side_names(letters: list[str]) -> list[str]:
        return [(roster.get(L) or L).strip() for L in letters if (roster.get(L) or L).strip()]

    return matchup, side_names(letters1), side_names(letters2)


def compute_box_player_standings_rows(box_team: str, year: int) -> list[dict]:
    """Season-to-date games won per letter/player for one box; mirrors static/app.js getBoxPlayerTotals."""
    roster = get_box_roster_dict(box_team, year)
    totals = {L: 0 for L in "ABCDEF"}
    with get_db() as conn:
        rows = conn.execute(
            """SELECT week, team1, team2, games1, games2 FROM scores
               WHERE league = 'box' AND level = ? AND (year = ? OR (year IS NULL AND ? IS NULL))""",
            (box_team, year, year),
        ).fetchall()
    by_week = {int(r["week"]): r for r in rows}

    for idx, matchup in enumerate(FULL_BOX_MATCHUPS):
        week_num = idx + 1
        r = by_week.get(week_num)
        if not r:
            continue
        try:
            g1 = int(r["games1"])
            g2 = int(r["games2"])
        except (TypeError, ValueError):
            continue
        side1, side2 = _parse_box_matchup_sides(matchup)
        if len(side1) != 2 or len(side2) != 2:
            continue
        s1_set, s2_set = frozenset(side1), frozenset(side2)
        db_a = _side_label_to_two_letters(r["team1"] or "")
        db_b = _side_label_to_two_letters(r["team2"] or "")
        if db_a is None or db_b is None:
            continue
        if db_a == s1_set and db_b == s2_set:
            gs1, gs2 = g1, g2
        elif db_a == s2_set and db_b == s1_set:
            gs1, gs2 = g2, g1
        else:
            continue
        for L in side1:
            totals[L] += gs1
        for L in side2:
            totals[L] += gs2

    out = [{"letter": L, "name": (roster.get(L) or "").strip(), "total": totals[L]} for L in "ABCDEF"]
    out.sort(key=lambda x: (-x["total"], x["letter"]))
    return out


def handicap_schedule_player_norms_for_level(conn, level: str, year: int) -> set:
    """Normalized player names on the handicap schedule for this division and season (all weeks)."""
    norms = set()
    rows = conn.execute(
        """SELECT team1, team2, team1_players, team2_players FROM schedule
           WHERE level = ? AND (year = ? OR year IS NULL)""",
        (level, year),
    ).fetchall()
    for r in rows:
        for p in players_for_schedule_match(
            level, r["team1"] or "", r["team2"] or "", r["team1_players"] or "", r["team2_players"] or ""
        ):
            norms.add(normalize_name(p))
    return norms


def normalized_player_handicap_levels_for_year(conn, year: int) -> dict[str, set[str]]:
    """
    Map normalized player name -> {'open', 'main'} for handicap schedule rows in that season.
    Used so match/standings emails only go to subscribers in the relevant division.
    """
    rows = conn.execute(
        """SELECT level, team1, team2, team1_players, team2_players FROM schedule
           WHERE level IN ('open', 'main') AND (year = ? OR year IS NULL)""",
        (year,),
    ).fetchall()
    out: dict[str, set[str]] = {}
    for r in rows:
        lev = (r["level"] or "").strip().lower()
        if lev not in ("open", "main"):
            continue
        for p in players_for_schedule_match(
            lev, r["team1"] or "", r["team2"] or "", r["team1_players"] or "", r["team2_players"] or ""
        ):
            k = normalize_name(p)
            if not k:
                continue
            out.setdefault(k, set()).add(lev)
    return out


def normalized_names_on_box_for_year(conn, box_team: str, year: int) -> set[str]:
    """
    Normalized names for anyone on this box tab roster for the season, plus any names
    already present on saved box scores for this team/year (sub names must match).
    """
    norms: set[str] = set()
    roster = get_box_roster_dict(box_team, year)
    for v in roster.values():
        k = normalize_name(str(v))
        if k:
            norms.add(k)
    rows = conn.execute(
        """SELECT team1_players, team2_players FROM scores
           WHERE league = 'box' AND level = ? AND (year = ? OR year IS NULL)""",
        (box_team, year),
    ).fetchall()
    for r in rows:
        for p in split_player_names(r["team1_players"]) + split_player_names(r["team2_players"]):
            k = normalize_name(p)
            if k:
                norms.add(k)
    return norms


def maybe_send_box_standings_digest_notifications(box_team: str, week: int, year: int, *, now_et: datetime) -> int:
    """
    Email notify_box subscribers (roster/name matched) a season standings snapshot for their box
    after each round's last day at STANDINGS_SEND_HOUR_ET (default 8 PM; cron-driven — not on POST /api/scores).

    One email per subscriber per (box, week, year); idempotent via box_score_notifications_sent.
    """
    deadline = box_week_deadline_date(box_team, week, year)
    if deadline is None:
        log.info(
            "Box standings digest skipped (team=%s week=%s year=%s): no schedule date label for this week",
            box_team,
            week,
            year,
        )
        return 0
    if not notification_delivery_allowed_after_deadline(deadline, now_et):
        return 0

    init_db()
    if box_team not in BOX_TEAM_NAMES:
        return 0

    date_label = ""
    dl = get_box_week_dates_label(box_team, week, year)
    if dl:
        date_label = f" ({dl})"

    standings_rows = compute_box_player_standings_rows(box_team, year)
    lines = []
    for i, row in enumerate(standings_rows, start=1):
        display = row["name"] or row["letter"]
        lines.append(f"{i}. {display} — {row['total']} games won")
    standings_text = "\n".join(lines) if lines else "No recorded scores yet."

    subject = f"River City Doubles: {box_team} standings after week {week}"
    base_body = (
        f"Season year {year}. Standings through week {week}{date_label} "
        f"(games won per player, same as the site box standings tab):\n\n"
        f"{standings_text}\n"
    )

    html_ranked = "".join(
        (
            "<tr>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{i}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db'>{row['name'] or row['letter']}</td>"
            f"<td style='padding:8px;border:1px solid #d1d5db;text-align:center'>{row['total']}</td>"
            "</tr>"
        )
        for i, row in enumerate(standings_rows, start=1)
    )
    _name_ph = "{name}"
    html_body = f"""
<html>
  <body style="font-family:Arial,sans-serif;color:#111827">
    <p>Hi {_name_ph},</p>
    <p>Season year {year}. Standings through week {week}{date_label} (games won per player).</p>
    <table style='border-collapse:collapse;min-width:420px'>
      <thead>
        <tr style='background:#f3f4f6'>
          <th style='padding:8px;border:1px solid #d1d5db'>#</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Player</th>
          <th style='padding:8px;border:1px solid #d1d5db'>Games won</th>
        </tr>
      </thead>
      <tbody>
        {html_ranked}
      </tbody>
    </table>
    <p style='margin-top:16px'>- River City Doubles</p>
  </body>
</html>
"""

    with get_db() as conn:
        subs = conn.execute(
            """SELECT name, email FROM email_subscriptions
               WHERE is_active = 1 AND notify_box = 1""",
        ).fetchall()
        roster_norms = normalized_names_on_box_for_year(conn, box_team, year)
        sent_rows = conn.execute(
            """SELECT email FROM box_score_notifications_sent
               WHERE level = ? AND week = ? AND year = ?""",
            (box_team, week, year),
        ).fetchall()
        sent_emails = {r["email"] for r in sent_rows}

    if not subs:
        return 0
    if not roster_norms:
        log.info(
            "Box standings digest skipped (team=%s week=%s year=%s): no roster or player names on scores for this box",
            box_team,
            week,
            year,
        )
        return 0

    sent_count = 0
    for s in subs:
        nn = normalize_name(s["name"])
        if nn not in roster_norms:
            continue
        if s["email"] in sent_emails:
            continue
        ok, err = send_match_notification_email(
            s["email"],
            s["name"],
            subject,
            base_body,
            html_body=html_body.replace("{name}", s["name"]),
        )
        if ok:
            sent_count += 1
            with get_db() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO box_score_notifications_sent
                       (email, level, week, year, sent_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (s["email"], box_team, week, year, now_iso()),
                )
                conn.commit()
            sent_emails.add(s["email"])
        else:
            log.warning("Box standings digest failed for %s: %s", s["email"], err)
    return sent_count


def maybe_send_box_match_play_reminders(box_team: str, week: int, year: int, *, now_et: datetime) -> int:
    """
    On the first morning of a box round (SEND_HOUR_ET US Eastern), email notify_box subscribers
    on that box roster about the week's matchup. Skips if a score is already saved for that week.
    One email per subscriber per (box, week, year); idempotent via box_match_reminders_sent.
    """
    week_start = box_week_start_date(box_team, week, year)
    if week_start is None:
        return 0
    if not notification_delivery_allowed_on_or_after_anchor(week_start, now_et):
        return 0
    bounds = box_week_date_bounds(box_team, week, year)
    if bounds and now_et.date() > bounds[1]:
        return 0

    init_db()
    if box_team not in BOX_TEAM_NAMES:
        return 0

    matchup, side1_names, side2_names = box_week_matchup_player_names(box_team, week, year)
    if not matchup or (not side1_names and not side2_names):
        log.info(
            "Box match reminder skipped (team=%s week=%s year=%s): no matchup or roster names",
            box_team,
            week,
            year,
        )
        return 0

    date_label = get_box_week_dates_label(box_team, week, year) or ""
    side1_txt = " & ".join(side1_names) if side1_names else "—"
    side2_txt = " & ".join(side2_names) if side2_names else "—"
    all_players = side1_names + side2_names

    with get_db() as conn:
        scored = conn.execute(
            """SELECT 1 FROM scores
               WHERE league = 'box' AND level = ? AND week = ?
                 AND (year = ? OR (year IS NULL AND ? IS NULL))
               LIMIT 1""",
            (box_team, week, year, year),
        ).fetchone()
        if scored:
            return 0
        subs = conn.execute(
            """SELECT name, email FROM email_subscriptions
               WHERE is_active = 1 AND notify_box = 1""",
        ).fetchall()
        roster_norms = normalized_names_on_box_for_year(conn, box_team, year)
        sent_rows = conn.execute(
            """SELECT email FROM box_match_reminders_sent
               WHERE level = ? AND week = ? AND year = ?""",
            (box_team, week, year),
        ).fetchall()
        sent_emails = {r["email"] for r in sent_rows}

    if not subs or not roster_norms:
        return 0

    subject = f"River City Doubles: {box_team} — week {week} match"
    sent_count = 0
    for s in subs:
        nn = normalize_name(s["name"])
        if nn not in roster_norms:
            continue
        if s["email"] in sent_emails:
            continue
        on_side = None
        for nm in all_players:
            if normalize_name(nm) == nn:
                if nm in side1_names:
                    on_side = side1_txt
                elif nm in side2_names:
                    on_side = side2_txt
                break
        side_note = f"\nYour side this week: {on_side}.\n" if on_side else ""
        body = (
            f"Your box \"{box_team}\" has a match for week {week}"
            f"{f' ({date_label})' if date_label else ''}.\n\n"
            f"Matchup: {matchup}\n"
            f"{side1_txt} vs {side2_txt}\n"
            f"{side_note}\n"
            "Enter scores on the site when your match is done.\n"
        )
        ok, err = send_match_notification_email(s["email"], s["name"], subject, body)
        if ok:
            sent_count += 1
            with get_db() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO box_match_reminders_sent
                       (email, level, week, year, sent_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (s["email"], box_team, week, year, now_iso()),
                )
                conn.commit()
            sent_emails.add(s["email"])
        else:
            log.warning("Box match reminder failed for %s: %s", s["email"], err)
    return sent_count


def sweep_box_match_reminders_for_season_years(now_et: datetime) -> int:
    """First-morning box match reminders for all teams/weeks with schedule labels in configured years."""
    allowed = set(SEASON_YEARS) if SEASON_YEARS else {DEFAULT_SEASON_YEAR}
    init_db()
    total = 0
    max_week = len(FULL_BOX_MATCHUPS)
    for y in allowed:
        for box_team in sorted(BOX_TEAM_NAMES):
            for week in range(1, max_week + 1):
                if get_box_week_dates_label(box_team, week, y) is None:
                    continue
                try:
                    total += maybe_send_box_match_play_reminders(box_team, week, y, now_et=now_et)
                except Exception as e:
                    log.warning(
                        "Box match reminder sweep failed team=%s week=%s year=%s: %s",
                        box_team,
                        week,
                        y,
                        e,
                    )
    return total


def sweep_box_standings_notifications_for_season_years(now_et: datetime) -> int:
    """
    Send box standings digests for saved scores in configured season years when this cron tick is
    on or after that round's last day at STANDINGS_SEND_HOUR_ET (default 8 PM). Idempotent via box_score_notifications_sent.
    """
    allowed = set(SEASON_YEARS) if SEASON_YEARS else {DEFAULT_SEASON_YEAR}
    init_db()
    total = 0
    with get_db() as conn:
        rows = conn.execute(
            """SELECT DISTINCT level, week, year FROM scores WHERE league = 'box'"""
        ).fetchall()
    for r in rows:
        box_team = (r["level"] or "").strip()
        week = int(r["week"])
        y_raw = r["year"]
        y = int(y_raw) if y_raw is not None else DEFAULT_SEASON_YEAR
        if y_raw is not None and y not in allowed:
            continue
        try:
            total += maybe_send_box_standings_digest_notifications(box_team, week, y, now_et=now_et)
        except Exception as e:
            log.warning(
                "Box standings digest sweep failed team=%s week=%s year=%s: %s",
                box_team,
                week,
                y,
                e,
            )
    return total


def maybe_send_match_play_notifications(
    level,
    week,
    year,
    *,
    now_et: datetime | None = None,
    on_date: date | None = None,
    only_match: tuple[str, str] | None = None,
):
    """
    Notify subscribed players about unscored matches in this handicap week.

    Sends on or after the week's first calendar day at SEND_HOUR_ET (not every day of the week).
    only_match: if set, only evaluate that team pairing (not used by daily cron).
    """
    now_et = now_et or notification_now_et()
    on_date = on_date or now_et.date()
    try:
        week_start, week_end = handicap_week_date_bounds(week, year)
    except ValueError:
        return 0
    if not notification_delivery_allowed_on_or_after_anchor(week_start, now_et):
        log.info(
            "Match notifications skipped (level=%s week=%s year=%s): before first morning of week (%s)",
            level,
            week,
            year,
            week_start,
        )
        return 0
    if on_date > week_end:
        log.info(
            "Match notifications skipped (level=%s week=%s year=%s): %s after week end %s",
            level,
            week,
            year,
            on_date,
            week_end,
        )
        return 0
    init_db()
    with get_db() as conn:
        rows = conn.execute(
            """SELECT team1, team2, team1_players, team2_players
               FROM schedule
               WHERE level = ? AND week = ? AND (year = ? OR year IS NULL)
                 AND team1 IS NOT NULL AND TRIM(team1) <> ''
                 AND team2 IS NOT NULL AND TRIM(team2) <> ''
                 AND (bye IS NULL OR TRIM(bye) = '')
                 AND (score IS NULL OR TRIM(score) = '')""",
            (level, week, year),
        ).fetchall()
        subs = conn.execute(
            """SELECT name, email FROM email_subscriptions
               WHERE is_active = 1 AND notify_handicap = 1""",
        ).fetchall()
        sent_rows = conn.execute(
            """SELECT email, team1, team2 FROM match_notifications_sent
               WHERE level = ? AND week = ? AND year = ?""",
            (level, week, year),
        ).fetchall()
        sent_keys = {(r["email"], r["team1"], r["team2"]) for r in sent_rows}
        player_levels = normalized_player_handicap_levels_for_year(conn, year)

    if only_match:
        a, b = (only_match[0] or "").strip(), (only_match[1] or "").strip()
        pair = tuple(sorted([a, b]))
        rows = [r for r in rows if tuple(sorted([(r["team1"] or "").strip(), (r["team2"] or "").strip()])) == pair]

    if not rows or not subs:
        log.info(
            "Match notifications skipped (level=%s week=%s year=%s): unscored_rows=%d handicap_subscribers=%d",
            level,
            week,
            year,
            len(rows),
            len(subs),
        )
        return 0

    sub_by_name = {normalize_name(s["name"]): s for s in subs}
    any_send_attempted = False
    sent_count = 0
    for row in rows:
        players = players_for_schedule_match(
            level,
            row["team1"] or "",
            row["team2"] or "",
            row["team1_players"] or "",
            row["team2_players"] or "",
        )
        if not players:
            continue
        players_norm = {normalize_name(p) for p in players}
        recipients = []
        for n_norm in players_norm:
            s = sub_by_name.get(n_norm)
            if not s:
                continue
            divs = player_levels.get(n_norm)
            if not divs or level not in divs:
                continue
            key = (s["email"], row["team1"] or "", row["team2"] or "")
            if key in sent_keys:
                continue
            recipients.append(s)
        if not recipients:
            continue
        any_send_attempted = True
        subject = f"River City Doubles: You are scheduled to play (Week {week})"
        body = (
            f"You are listed in an upcoming {level.title()} handicap match.\n"
            f"Week {week} ({WEEK_DATE_RANGES.get(week, '')}), season {year}-{year + 1}\n"
            f"{row['team1']} vs {row['team2']}\n"
        )
        to_emails = [r["email"] for r in recipients]
        ok, err = send_match_notification_email(to_emails, "players", subject, body)
        if ok:
            sent_count += len(recipients)
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
            log.warning("Match notification group email failed (%s): %s", to_emails, err)

    if subs and rows and not any_send_attempted:
        with_players = sum(
            1
            for r in rows
            if players_for_schedule_match(
                level,
                r["team1"] or "",
                r["team2"] or "",
                r["team1_players"] or "",
                r["team2_players"] or "",
            )
        )
        if with_players == 0:
            log.info(
                "Match notifications: %d unscored schedule row(s) but no player names in schedule; match emails need team1_players/team2_players",
                len(rows),
            )
        else:
            log.info(
                "Match notifications: %d subscriber(s) and %d row(s) with players, but no name match — subscription Name must match a player name on the schedule (same spelling)",
                len(subs),
                with_players,
            )
    return sent_count


def maybe_send_round_standings_notifications(level, week, year, *, now_et: datetime):
    """
    Send standings digest when all non-bye matches in a week have scores.

    Delivery is cron-driven: eligible on or after the week's last calendar day at SEND_HOUR_ET,
    not immediately when the final score is posted.

    Only subscribers whose saved name appears on the handicap schedule for this
    division (Open or Main) and season receive mail for that division's standings.
    """
    init_db()
    try:
        _, week_end = handicap_week_date_bounds(week, year)
    except ValueError:
        return 0
    if not notification_delivery_allowed_after_deadline(week_end, now_et):
        return 0

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
            log.info(
                "Standings email skipped (level=%s week=%s year=%s): expected_matches=%d completed_scores=%d",
                level,
                week,
                year,
                expected,
                completed,
            )
            return 0

        subs = conn.execute(
            """SELECT name, email FROM email_subscriptions
               WHERE is_active = 1 AND notify_handicap = 1""",
        ).fetchall()
        sent = conn.execute(
            """SELECT email FROM round_standings_notifications_sent
               WHERE level = ? AND week = ? AND year = ?""",
            (level, week, year),
        ).fetchall()
        sent_emails = {r["email"] for r in sent}
        player_norms = handicap_schedule_player_norms_for_level(conn, level, year)
        player_levels = normalized_player_handicap_levels_for_year(conn, year)

    if not subs:
        log.info(
            "Standings email skipped (level=%s week=%s): week complete but no subscribers with notify_handicap",
            level,
            week,
        )
        return 0
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
    _name_ph = "{name}"
    html_body = f"""
<html>
  <body style="font-family:Arial,sans-serif;color:#111827">
    <p>Hi {_name_ph},</p>
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
    if not player_norms:
        log.info(
            "Standings email skipped (level=%s week=%s year=%s): no player names on schedule for this division; add team1_players/team2_players to match subscribers",
            level,
            week,
            year,
        )
        return 0
    before_filter = len(pending)
    pending = [
        s
        for s in pending
        if level in player_levels.get(normalize_name(s["name"]), set())
    ]
    if before_filter and not pending:
        log.info(
            "Standings email skipped (level=%s week=%s): no subscriber names matched schedule players for this division",
            level,
            week,
        )
        return 0
    if not pending:
        return 0
    sent_count = 0
    for s in pending:
        ok, err = send_match_notification_email(
            s["email"],
            s["name"],
            subject,
            base_body,
            html_body=html_body.replace("{name}", s["name"]),
        )
        if ok:
            sent_count += 1
            with get_db() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO round_standings_notifications_sent
                       (email, level, week, year, sent_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (s["email"], level, week, year, now_iso()),
                )
                conn.commit()
        else:
            log.warning("Standings email failed for %s: %s", s["email"], err)
    return sent_count


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
    except _DB_API_ERRORS:
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


@app.route("/api/build-info")
def build_info():
    """Client uses this to detect a new deploy and optionally force a one-time hard refresh (SW + caches)."""
    return jsonify({"asset_version": ASSET_VERSION, "reload_bump": CLIENT_RELOAD_BUMP}), 200


@app.route("/")
def index():
    path = os.path.join(STATIC_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read().replace("__ASSET_VERSION__", ASSET_VERSION)
    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/sw.js")
def service_worker():
    path = os.path.join(STATIC_DIR, "sw.js")
    with open(path, "r", encoding="utf-8") as f:
        js = f.read().replace("__ASSET_VERSION__", ASSET_VERSION)
    resp = Response(js, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


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
    # Prefer new league flags; fall back to legacy keys for older clients.
    if "notify_handicap" in data or "notify_box" in data:
        notify_handicap = bool(data.get("notify_handicap", False))
        notify_box = bool(data.get("notify_box", False))
    else:
        notify_handicap = bool(data.get("notify_match", True)) or bool(
            data.get("notify_round_standings", False)
        )
        notify_box = bool(data.get("notify_box", False))
    is_active = notify_handicap or notify_box
    # Keep legacy columns aligned with handicap bucket (match + standings use same gate).
    notify_match = 1 if notify_handicap else 0
    notify_round_standings = 1 if notify_handicap else 0
    if not name:
        return jsonify({"error": "First and last name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    init_db()
    ts = now_iso()
    welcome_email_sent = False
    welcome_email_error = None
    was_active = False
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, is_active FROM email_subscriptions WHERE email = ?",
            (email,),
        ).fetchone()
        is_new = existing is None
        if existing:
            was_active = bool(existing["is_active"])
            conn.execute(
                """UPDATE email_subscriptions
                   SET name = ?, is_active = ?, notify_match = ?, notify_round_standings = ?,
                       notify_handicap = ?, notify_box = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    name,
                    1 if is_active else 0,
                    notify_match,
                    notify_round_standings,
                    1 if notify_handicap else 0,
                    1 if notify_box else 0,
                    ts,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """INSERT INTO email_subscriptions
                   (name, email, is_active, notify_match, notify_round_standings,
                    notify_handicap, notify_box, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    email,
                    1 if is_active else 0,
                    notify_match,
                    notify_round_standings,
                    1 if notify_handicap else 0,
                    1 if notify_box else 0,
                    ts,
                    ts,
                ),
            )
        conn.commit()
    should_send_welcome = is_active and (is_new or not was_active)
    if should_send_welcome:
        ok, err = maybe_send_subscription_welcome(email, name, notify_handicap, notify_box)
        welcome_email_sent = bool(ok)
        if not ok:
            welcome_email_error = err or "Send failed (check server logs and Brevo sender verification)"
            if _email_transport_configured():
                log.warning("Subscription welcome email failed for %s: %s", email, welcome_email_error)
            else:
                welcome_email_error = "Email not configured on server (RCD_SMTP_PASS or RCD_RESEND_API_KEY)"
    resp = {
        "ok": True,
        "email": email,
        "is_active": is_active,
        "notify_handicap": notify_handicap,
        "notify_box": notify_box,
        "welcome_email_sent": welcome_email_sent,
    }
    if welcome_email_error:
        resp["welcome_email_error"] = welcome_email_error
    return jsonify(resp), 200


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
               SET is_active = 0, notify_match = 0, notify_round_standings = 0,
                   notify_handicap = 0, notify_box = 0, updated_at = ?
               WHERE email = ?""",
            (now_iso(), email),
        )
        conn.commit()
    return jsonify({"ok": True, "email": email, "is_active": False}), 200


@app.route("/api/notifications/status")
def notification_email_status():
    """Whether outbound email is configured (no secrets). Check Render logs if sends still fail."""
    resend = bool(os.environ.get("RCD_RESEND_API_KEY", "").strip())
    brevo_api = bool(os.environ.get("RCD_BREVO_API_KEY", "").strip())
    smtp_pass = os.environ.get("RCD_SMTP_PASS", "").strip()
    from_email = os.environ.get("RCD_EMAIL_FROM", "").strip()
    return jsonify(
        {
            "turso_configured": use_turso(),
            "email_transport_configured": _email_transport_configured(),
            "resend_configured": resend,
            "brevo_api_configured": brevo_api,
            "smtp_configured": bool(smtp_pass),
            "from_email_hint": (from_email[:3] + "…" if len(from_email) > 3 else "") if from_email else "using default From (set RCD_EMAIL_FROM to your Brevo-verified sender)",
            "smtp_host": os.environ.get("RCD_SMTP_HOST", "smtp.sendgrid.net").strip(),
            "smtp_port": int(os.environ.get("RCD_SMTP_PORT", "587")),
            "smtp_ssl": os.environ.get("RCD_SMTP_SSL", "").strip().lower() in ("1", "true", "yes"),
            "smtp_user_set": bool(os.environ.get("RCD_SMTP_USER", "").strip()),
            "from_email_set": bool(from_email),
            "test_endpoint_enabled": bool(os.environ.get("RCD_NOTIFICATION_TEST_SECRET", "").strip()),
            "cron_endpoint_enabled": bool(os.environ.get("RCD_CRON_SECRET", "").strip()),
        }
    ), 200


@app.route("/api/notifications/test-email", methods=["POST"])
def notification_test_email():
    """
    Send a single test message if RCD_NOTIFICATION_TEST_SECRET or RCD_CRON_SECRET is set.
    Body: {"secret": "<same as env>", "to": "you@example.com", "kind": "smtp"|"example"}
    Header alternative: X-RCD-Cron: <RCD_CRON_SECRET>
    """
    if not (
        os.environ.get("RCD_NOTIFICATION_TEST_SECRET", "").strip()
        or os.environ.get("RCD_CRON_SECRET", "").strip()
    ):
        return jsonify({"error": "Test endpoint disabled (set RCD_NOTIFICATION_TEST_SECRET or RCD_CRON_SECRET)"}), 404
    data = request.get_json(silent=True) or {}
    supplied = (data.get("secret") or "").strip() or (request.headers.get("X-RCD-Cron") or "").strip()
    if not _notification_admin_secret_ok(supplied):
        return jsonify({"error": "Invalid secret"}), 401
    to = (data.get("to") or "").strip().lower()
    if not to or "@" not in to:
        return jsonify({"error": "Provide a valid to address"}), 400
    kind = (data.get("kind") or "smtp").strip().lower()
    name = " ".join((data.get("name") or "there").strip().split()) or "there"
    try:
        if kind == "example":
            ok, err = send_example_notification_email(to, name)
        else:
            ok, err = send_match_notification_email(
                to,
                name,
                "River City Doubles: SMTP test",
                "If you received this, SMTP is working. You can remove RCD_NOTIFICATION_TEST_SECRET after testing.",
            )
    except Exception as e:
        log.exception("test-email unexpected error")
        return jsonify({"ok": False, "error": str(e)}), 500
    if ok:
        return jsonify({"ok": True, "kind": kind, "to": to}), 200
    return jsonify({"ok": False, "error": err}), 500


@app.route("/api/notifications/example-email", methods=["POST"])
def notification_example_email():
    """
    Send the sample handicap/box notification email.
    Auth: JSON {"secret": "..."} or header X-RCD-Cron (RCD_CRON_SECRET or RCD_NOTIFICATION_TEST_SECRET).
    Body: {"to": "you@example.com", "name": "First Last"}
    """
    if not (
        os.environ.get("RCD_NOTIFICATION_TEST_SECRET", "").strip()
        or os.environ.get("RCD_CRON_SECRET", "").strip()
    ):
        return jsonify({"error": "Example email disabled (set RCD_CRON_SECRET or RCD_NOTIFICATION_TEST_SECRET)"}), 404
    data = request.get_json(silent=True) or {}
    supplied = (data.get("secret") or "").strip() or (request.headers.get("X-RCD-Cron") or "").strip()
    if not _notification_admin_secret_ok(supplied):
        return jsonify({"error": "Invalid secret"}), 401
    to = (data.get("to") or "").strip().lower()
    if not to or "@" not in to:
        return jsonify({"error": "Provide a valid to address"}), 400
    name = " ".join((data.get("name") or "there").strip().split()) or "there"
    ok, err = send_example_notification_email(to, name)
    if ok:
        return jsonify({"ok": True, "to": to}), 200
    return jsonify({"ok": False, "error": err}), 500


def run_notification_checks_for_today(on_date: date | None = None, now_et: datetime | None = None):
    """
    Notification cron: handicap/box match reminders on or after each round's first morning (SEND_HOUR_ET);
    handicap standings when the week is score-complete and on or after 8 PM on that week's last day;
    box standings digests on the same evening rule. Nothing is sent from POST /api/scores.
    """
    now_et = now_et or notification_now_et()
    on_date = on_date or now_et.date()
    year = handicap_season_year_for_date(on_date)
    ctx = notification_weeks_for_date(on_date, year) if year is not None else {}
    stats = {
        "date": on_date.isoformat(),
        "season_year": year,
        "match_week": ctx.get("match_week"),
        "standings_weeks": ctx.get("standings_weeks", []),
        "match_emails_sent": 0,
        "standings_emails_sent": 0,
        "box_match_emails_sent": 0,
        "box_emails_sent": 0,
        "errors": 0,
        "skipped": None,
    }
    try:
        stats["box_match_emails_sent"] = sweep_box_match_reminders_for_season_years(now_et)
    except Exception as e:
        stats["errors"] += 1
        log.warning("Box match reminder sweep failed: %s", e)
    try:
        stats["box_emails_sent"] = sweep_box_standings_notifications_for_season_years(now_et)
    except Exception as e:
        stats["errors"] += 1
        log.warning("Box standings notification sweep failed: %s", e)

    if year is None:
        stats["skipped"] = "no active handicap season for this date"
        log.info("Notification cron skipped: %s (%s)", stats["skipped"], on_date)
        return stats

    match_week = ctx.get("match_week")
    if match_week is None:
        log.info(
            "Notification cron: no handicap match week for date=%s season_year=%s (match reminders skipped)",
            on_date,
            year,
        )
    else:
        for level in ("open", "main"):
            try:
                stats["match_emails_sent"] += (
                    maybe_send_match_play_notifications(
                        level, match_week, year, now_et=now_et, on_date=on_date
                    )
                    or 0
                )
            except Exception as e:
                stats["errors"] += 1
                log.warning(
                    "Notification tick failed level=%s week=%s year=%s: %s",
                    level,
                    match_week,
                    year,
                    e,
                )

    standings_weeks = ctx.get("standings_weeks") or []
    for level in ("open", "main"):
        for week in standings_weeks:
            try:
                stats["standings_emails_sent"] += (
                    maybe_send_round_standings_notifications(level, week, year, now_et=now_et) or 0
                )
            except Exception as e:
                stats["errors"] += 1
                log.warning(
                    "Standings notification failed level=%s week=%s year=%s: %s",
                    level,
                    week,
                    year,
                    e,
                )
    return stats


@app.route("/api/cron/notifications", methods=["POST", "GET"])
def cron_notifications():
    """
    Wake the notification logic on a schedule (Render Cron, GitHub Actions, etc.).
    Set RCD_CRON_SECRET; send the same value as header X-RCD-Cron, JSON body secret, or ?secret= (GET is weaker).

    Example (Render Cron Job, daily):
      curl -X POST -H "X-RCD-Cron: YOUR_SECRET" https://your-app.onrender.com/api/cron/notifications
    """
    expected = os.environ.get("RCD_CRON_SECRET", "").strip()
    if not expected:
        return jsonify({"error": "Cron disabled (set RCD_CRON_SECRET)"}), 404
    supplied = (request.headers.get("X-RCD-Cron") or "").strip()
    if not supplied and request.method == "POST":
        data = request.get_json(silent=True) or {}
        supplied = (data.get("secret") or "").strip()
    if not supplied:
        supplied = (request.args.get("secret") or "").strip()
    if supplied != expected:
        return jsonify({"error": "Invalid secret"}), 401
    try:
        stats = run_notification_checks_for_today()
        return jsonify({"ok": True, **stats}), 200
    except Exception as e:
        log.exception("Cron notification run failed")
        return jsonify({"ok": False, "error": str(e)}), 500


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


@app.route("/api/box/scores", methods=["GET"])
def get_box_scores():
    """Return saved box-league scores for one box and season (for client standings/schedule aggregation)."""
    team = (request.args.get("team") or "").strip()
    year = request.args.get("year", type=int)
    if year is None:
        year = DEFAULT_SEASON_YEAR
    if team not in BOX_TEAM_NAMES:
        return jsonify({"error": "Invalid box name"}), 400
    try:
        ensure_db_ready()
        with get_db() as conn:
            rows = conn.execute(
                """SELECT week, team1, team2, games1, games2, team1_players, team2_players, year
                   FROM scores
                   WHERE league = 'box' AND level = ? AND (year = ? OR year IS NULL)
                   ORDER BY week""",
                (team, year),
            ).fetchall()
    except _DB_API_ERRORS as e:
        return jsonify({"error": "Database error", "detail": str(e)}), 500
    out = []
    for r in rows:
        out.append(
            {
                "week": int(r["week"]),
                "team1": r["team1"] or "",
                "team2": r["team2"] or "",
                "games1": int(r["games1"]),
                "games2": int(r["games2"]),
                "team1_players": r["team1_players"] or "",
                "team2_players": r["team2_players"] or "",
                "year": r["year"],
            }
        )
    return jsonify(out), 200


@app.route("/api/scores", methods=["POST"])
def post_score():
    data = request.get_json() or {}
    league = (data.get("league") or "").strip().lower()
    level_raw = (data.get("level") or "").strip()
    # Handicap levels are open/main (case-insensitive). Box names must keep original casing.
    level = level_raw.lower() if league == "handicap" else level_raw
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
        year = DEFAULT_SEASON_YEAR

    if league not in ("box", "handicap"):
        return jsonify({"error": "Invalid league"}), 400

    if league == "handicap":
        if level not in ("open", "main"):
            return jsonify({"error": "Invalid level for handicap"}), 400
        allowed = [t for t in (TEAMS_OPEN if level == "open" else TEAMS_MAIN) if t not in TEAMS_EXCLUDED]
        if team1 not in allowed or team2 not in allowed:
            return jsonify({"error": "Invalid team name for this level"}), 400
    else:
        # Box: level is the box name; team1/team2 are sides like "A & D" (not handicap team names).
        if level not in BOX_TEAM_NAMES:
            return jsonify({"error": "Invalid box name"}), 400
        if not team1 or not team2:
            return jsonify({"error": "Both team sides are required"}), 400
        if len(team1) > 200 or len(team2) > 200:
            return jsonify({"error": "Team side label too long"}), 400

    if team1 == team2:
        return jsonify({"error": "Team 1 and Team 2 must be different"}), 400
    if not isinstance(week, int) or week < 1:
        return jsonify({"error": "Week must be a positive integer"}), 400
    if not (0 <= games1 <= 3 and 0 <= games2 <= 3):
        return jsonify({"error": "No team can win more than 3 games"}), 400
    if games1 + games2 > 5:
        return jsonify({"error": "Best of 5: total games cannot exceed 5"}), 400

    # Normalize handicap match order against schedule; box sides stay as submitted.
    if league == "handicap" and level in ("open", "main"):
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
        # Handicap schedule spreadsheet only (not box league).
        if league == "handicap" and level in ("open", "main"):
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
        year = DEFAULT_SEASON_YEAR

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
    except _DB_API_ERRORS as e:
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
        year = DEFAULT_SEASON_YEAR
    try:
        ensure_db_ready()
        with get_db() as conn:
            rows = conn.execute(
                """SELECT id, week, date_range, team1, team2, bye, team1_players, team2_players,
                          handicap, score, winner FROM schedule WHERE level = ? AND (year = ? OR year IS NULL) ORDER BY week, id""",
                (level, year),
            ).fetchall()
    except _DB_API_ERRORS as e:
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
    # Match reminders are sent by the daily cron, not when schedule rows are posted.
    return jsonify({"ok": True}), 201


if __name__ == "__main__":
    init_db()
    try:
        with get_db() as conn:
            n = conn.execute(
                "SELECT COUNT(*) AS c FROM scores WHERE league = ? AND level IN ('open', 'main')",
                ("handicap",),
            ).fetchone()["c"]
        label = "Turso (libsql)" if use_turso() else DB_PATH
        print(f"Using database: {label} ({n} handicap scores)")
    except Exception as e:
        label = "Turso (libsql)" if use_turso() else DB_PATH
        print(f"Using database: {label} (check failed: {e})")
    app.run(debug=True, port=5000)
