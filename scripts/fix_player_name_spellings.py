#!/usr/bin/env python3
"""Replace legacy player name spellings in schedule, scores, and email_subscriptions.

Uses RCD_DB or Turso (TURSO_DATABASE_URL + TURSO_AUTH_TOKEN) via rcd_db.get_db().
Run from repo root: python scripts/fix_player_name_spellings.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from rcd_db import get_db, use_turso  # noqa: E402

# (old, new) — apply in order; no substring overlap between old values.
REPLACEMENTS: list[tuple[str, str]] = [
    ("Dave Shepardson", "David Shepardson"),
    ("Frank Devenoge", "Frank De Venoge"),
    ("Skye Phillips", "Skylyr Phillips"),
    ("Skye Philips", "Skylyr Phillips"),
]


def _count_contains(conn, table: str, column: str, needle: str) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) AS c FROM {table} WHERE instr({column}, ?) > 0",
        (needle,),
    ).fetchone()
    return int(row["c"] if hasattr(row, "keys") else row[0])


def main() -> None:
    target = "Turso" if use_turso() else os.environ.get("RCD_DB", "scores.db (default)")
    print(f"Database: {target}")

    total_updates = 0
    with get_db() as conn:
        for table, columns in (
            ("schedule", ("team1_players", "team2_players")),
            ("scores", ("team1_players", "team2_players")),
            ("email_subscriptions", ("name",)),
        ):
            for col in columns:
                for old, new in REPLACEMENTS:
                    before = _count_contains(conn, table, col, old)
                    if not before:
                        continue
                    conn.execute(
                        f"UPDATE {table} SET {col} = REPLACE({col}, ?, ?) WHERE instr({col}, ?) > 0",
                        (old, new, old),
                    )
                    print(f"  {table}.{col}: {before} row(s) contained {old!r} -> {new!r}")
                    total_updates += before
        conn.commit()

    print(f"Done. Applied replacements across {total_updates} cell(s) (rows may be counted multiple times per column).")


if __name__ == "__main__":
    main()
