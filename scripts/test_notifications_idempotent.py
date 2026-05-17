#!/usr/bin/env python3
"""Verify notification cron is idempotent: two identical runs add no duplicate sent-log rows.

Runs ``run_notification_checks_for_today`` twice with the same ``now_et`` (fixed clock),
then asserts row counts in ``*_notifications_sent`` tables are unchanged after the second run.

This exercises SQLite UNIQUE + INSERT OR IGNORE dedupe (match / handicap standings / box digest).

**Warning:** This invokes real notification logic. If email is configured and eligibility gates pass,
the first run may send mail and insert rows; the second run must not insert duplicates.

Uses ``RCD_DB`` / Turso env from ``.env`` like other scripts (same DB as the Flask app).

Usage::

  # Deterministic instant (wall clock = US Eastern if no offset)
  python scripts/test_notifications_idempotent.py --at 2026-05-16T09:30:00

  # Same as above with explicit zone
  python scripts/test_notifications_idempotent.py --at 2026-05-16T09:30:00-05:00

  # Use current time twice (less reproducible but quick smoke test)
  python scripts/test_notifications_idempotent.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_ROOT, ".env"))
except ImportError:
    pass

from app import init_db, run_notification_checks_for_today  # noqa: E402
from rcd_db import get_db  # noqa: E402

_SENT_TABLES = (
    "match_notifications_sent",
    "round_standings_notifications_sent",
    "box_match_reminders_sent",
    "box_score_notifications_sent",
)


def snapshot_counts() -> dict[str, int]:
    init_db()
    out: dict[str, int] = {}
    with get_db() as conn:
        for table in _SENT_TABLES:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
            out[table] = int(row["c"])
    return out


def parse_now_et(arg: str | None) -> datetime:
    """Interpret CLI datetime for cron; default tz America/New_York when naive."""
    et = ZoneInfo("America/New_York")
    if arg is None:
        from app import notification_now_et

        return notification_now_et()
    raw = arg.strip()
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=et)
    return dt.astimezone(et)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--at",
        metavar="ISO_DATETIME",
        dest="at_iso",
        help="Fixed instant for both cron runs (e.g. 2026-05-16T09:30:00). Naive values use America/New_York.",
    )
    args = parser.parse_args()

    now_et = parse_now_et(args.at_iso)

    turso = os.environ.get("TURSO_DATABASE_URL", "").strip()
    db_hint = (turso[:48] + "…") if len(turso) > 48 else turso or os.environ.get("RCD_DB", os.path.join(_ROOT, "scores.db"))
    print(
        "Running notification cron twice at",
        now_et.isoformat(),
        "| DB:",
        db_hint,
        file=sys.stderr,
    )
    print(
        "If transports are configured, eligible recipients may receive email on the first pass only.",
        file=sys.stderr,
    )

    c0 = snapshot_counts()
    stats1 = run_notification_checks_for_today(now_et=now_et)
    c1 = snapshot_counts()
    stats2 = run_notification_checks_for_today(now_et=now_et)
    c2 = snapshot_counts()

    delta_first = {t: c1[t] - c0[t] for t in _SENT_TABLES}
    delta_second = {t: c2[t] - c1[t] for t in _SENT_TABLES}
    idempotent = all(delta_second[t] == 0 for t in _SENT_TABLES)

    report = {
        "now_et": now_et.isoformat(),
        "counts_before": c0,
        "counts_after_run1": c1,
        "counts_after_run2": c2,
        "rows_added_run1": delta_first,
        "rows_added_run2": delta_second,
        "stats_run1": stats1,
        "stats_run2": stats2,
        "idempotent_no_duplicate_sends_log_rows": idempotent,
    }
    print(json.dumps(report, indent=2, default=str))

    if not idempotent:
        print(
            "\nFAIL: Second run changed sent-log row counts (possible duplicate insert bug).",
            file=sys.stderr,
        )
        return 1
    print("\nOK: Sent-log counts unchanged after second identical cron run.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
