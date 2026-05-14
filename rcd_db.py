"""
Database access: local SQLite (RCD_DB) or Turso Cloud (TURSO_DATABASE_URL + TURSO_AUTH_TOKEN).
When Turso env vars are set, all app DB traffic uses libsql over HTTPS so Render redeploys do not wipe data.
"""
import logging
import os
import sqlite3

log = logging.getLogger("rcd")

DB_PATH = os.environ.get("RCD_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.db"))
_db_parent = os.path.dirname(os.path.abspath(DB_PATH))
if _db_parent:
    try:
        os.makedirs(_db_parent, exist_ok=True)
    except OSError as e:
        log.warning("Could not create database directory %s: %s", _db_parent, e)


def use_turso():
    return bool(
        os.environ.get("TURSO_DATABASE_URL", "").strip()
        and os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    )


def ensure_schema():
    """Create tables if missing (idempotent). For Turso, run before seed scripts."""
    from app import init_db

    init_db()


def _cols_from_description(description):
    if not description:
        return []
    return [d[0] for d in description]


class DictRow:
    """sqlite3.Row–like access: row['col'], row[0], and tuple unpacking via iteration."""

    __slots__ = ("_t", "_m")

    def __init__(self, cols, tup):
        self._t = tup
        self._m = {cols[i]: tup[i] for i in range(len(cols))}

    def __getitem__(self, k):
        if isinstance(k, int):
            return self._t[k]
        return self._m[k]

    def __iter__(self):
        return iter(self._t)


class TursoCursorShim:
    __slots__ = ("_inner", "description")

    def __init__(self, inner):
        self._inner = inner
        self.description = inner.description

    def fetchone(self):
        row = self._inner.fetchone()
        if row is None:
            return None
        cols = _cols_from_description(self.description)
        return DictRow(cols, row)

    def fetchall(self):
        cols = _cols_from_description(self.description)
        return [DictRow(cols, r) for r in self._inner.fetchall()]


class TursoCompatConnection:
    __slots__ = ("_inner",)

    def __init__(self, inner):
        self._inner = inner

    def execute(self, sql, parameters=None):
        if parameters is None:
            cur = self._inner.execute(sql)
        elif isinstance(parameters, (tuple, list)):
            cur = self._inner.execute(sql, tuple(parameters))
        else:
            cur = self._inner.execute(sql, parameters)
        return TursoCursorShim(cur)

    def commit(self):
        self._inner.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._inner.__exit__(exc_type, exc, tb)


def get_db():
    if use_turso():
        import libsql

        inner = libsql.connect(
            database=os.environ["TURSO_DATABASE_URL"].strip(),
            auth_token=os.environ["TURSO_AUTH_TOKEN"].strip(),
        )
        return TursoCompatConnection(inner)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
