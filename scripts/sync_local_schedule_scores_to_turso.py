#!/usr/bin/env python3
"""
Copy schedule + scores from local SQLite to Turso (replaces those two tables on Turso).

Backs /api/schedule and handicap/box score data used by the Players tab (handicap side),
schedules, and standings.

Requires: TURSO_DATABASE_URL, TURSO_AUTH_TOKEN (same as production — use the real
libsql:// URL from the Turso dashboard, not a placeholder containing "…").
Source: RCD_DB or <repo>/scores.db

Usage (repo root):
  export TURSO_DATABASE_URL='libsql://your-db-your-org.turso.io'
  export TURSO_AUTH_TOKEN='eyJ...'
  python scripts/sync_local_schedule_scores_to_turso.py
  python scripts/sync_local_schedule_scores_to_turso.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _local_db_path() -> str:
    return os.environ.get(
        "RCD_DB",
        os.path.join(_ROOT, "scores.db"),
    )


def _fetch_all(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[tuple]]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = [tuple(r[c] for c in cols) for r in cur.fetchall()]
    return cols, rows


def _validate_turso_env() -> None:
    """Fail fast with a clear message if the URL looks like a doc placeholder."""
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not url or not token:
        raise SystemExit(
            "Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN before running (not using --dry-run)."
        )
    if "\u2026" in url or "\u2026" in token:
        raise SystemExit(
            "TURSO_DATABASE_URL (or token) contains a Unicode ellipsis (…). "
            "Use the exact libsql:// URL and token from the Turso dashboard — do not paste the … placeholder from docs."
        )
    if url in ("libsql://…", "libsql://...", "https://…", "https://..."):
        raise SystemExit(
            "TURSO_DATABASE_URL is still a placeholder. Copy the full URL from Turso → your database → Connect."
        )
    if not (url.startswith("libsql://") or url.startswith("https://")):
        raise SystemExit(
            f"TURSO_DATABASE_URL should start with libsql:// or https:// (got prefix: {url[:32]!r})."
        )
    if any(c in url for c in " \t\n\r<>"):
        raise SystemExit(
            "TURSO_DATABASE_URL contains whitespace or angle brackets; paste only the URL string."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print local row counts only; do not connect to Turso.",
    )
    args = parser.parse_args()

    local_path = _local_db_path()
    if not os.path.isfile(local_path):
        raise SystemExit(f"Local database not found: {local_path}")

    local = sqlite3.connect(local_path)
    try:
        sch_cols, sch_rows = _fetch_all(local, "schedule")
        sc_cols, sc_rows = _fetch_all(local, "scores")
    finally:
        local.close()

    print(f"Local {local_path}: schedule={len(sch_rows)} rows, scores={len(sc_rows)} rows")

    if args.dry_run:
        print("Dry run: no Turso writes.")
        return

    _validate_turso_env()

    from app import init_db  # noqa: E402
    from rcd_db import get_db  # noqa: E402

    init_db()
    ph_sch = ",".join("?" * len(sch_cols))
    sql_ins_sch = f"INSERT INTO schedule ({','.join(sch_cols)}) VALUES ({ph_sch})"
    ph_sc = ",".join("?" * len(sc_cols))
    sql_ins_sc = f"INSERT INTO scores ({','.join(sc_cols)}) VALUES ({ph_sc})"

    with get_db() as conn:
        conn.execute("DELETE FROM scores")
        conn.execute("DELETE FROM schedule")
        for tup in sch_rows:
            conn.execute(sql_ins_sch, tup)
        for tup in sc_rows:
            conn.execute(sql_ins_sc, tup)
        conn.commit()

    print(f"Turso: replaced schedule ({len(sch_rows)} rows) and scores ({len(sc_rows)} rows).")


if __name__ == "__main__":
    main()
