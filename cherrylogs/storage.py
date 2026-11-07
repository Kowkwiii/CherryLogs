"""SQLite storage for imported logs and import history.

The database lives in %APPDATA%\\CherryLogs\\cherrylogs.db on Windows.
Every thread must use its own Storage instance (SQLite connections are not
shared between threads); WAL mode lets them work side by side.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime
from typing import Iterable, Optional

from .models import Entry, ImportInfo, ParsedLog

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL UNIQUE,
    size        INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    log_date    TEXT NOT NULL DEFAULT '',
    first_ts    TEXT NOT NULL DEFAULT '',
    last_ts     TEXT NOT NULL DEFAULT '',
    line_count  INTEGER NOT NULL DEFAULT 0,
    entry_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entries (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    line_no   INTEGER NOT NULL,
    ts        TEXT NOT NULL,
    category  TEXT NOT NULL,
    event     TEXT NOT NULL,
    level     TEXT NOT NULL,
    thread    TEXT NOT NULL,
    player    TEXT NOT NULL,
    players   TEXT NOT NULL,
    extra     TEXT NOT NULL,
    message   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_import ON entries(import_id);
"""


def default_db_path() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"),
                                                      ".cherrylogs")
    folder = os.path.join(base, "CherryLogs")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "cherrylogs.db")


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Storage:
    def __init__(self, path: Optional[str] = None):
        self.path = path or default_db_path()
        self.conn = sqlite3.connect(self.path, timeout=30)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------ imports
    def find_import_by_hash(self, sha: str) -> Optional[int]:
        row = self.conn.execute("SELECT id FROM imports WHERE sha256 = ?",
                                (sha,)).fetchone()
        return row[0] if row else None

    def add_import(self, name: str, path: str, sha: str, size: int,
                   parsed: ParsedLog) -> int:
        with self.conn:  # one transaction
            cur = self.conn.execute(
                "INSERT INTO imports (name, path, sha256, size, imported_at,"
                " log_date, first_ts, last_ts, line_count, entry_count)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (name, path, sha, size,
                 datetime.now().isoformat(sep=" ", timespec="seconds"),
                 parsed.log_date, parsed.first_ts, parsed.last_ts,
                 parsed.line_count, len(parsed.entries)))
            import_id = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO entries (import_id, line_no, ts, category, event,"
                " level, thread, player, players, extra, message)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ((import_id, e.line_no, e.ts.isoformat(sep=" "), e.category,
                  e.event, e.level, e.thread, e.player, ",".join(e.players),
                  e.extra, e.message) for e in parsed.entries))
        return import_id

    def list_imports(self) -> list:
        rows = self.conn.execute(
            "SELECT id, name, path, sha256, size, imported_at, log_date,"
            " first_ts, last_ts, line_count, entry_count FROM imports"
            " ORDER BY log_date DESC, id DESC").fetchall()
        return [ImportInfo(*r) for r in rows]

    def existing_ids(self, ids: Iterable) -> list:
        ids = list(ids)
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT id FROM imports WHERE id IN ({marks})", ids).fetchall()
        return [r[0] for r in rows]

    def import_names(self) -> dict:
        return {r[0]: r[1] for r in
                self.conn.execute("SELECT id, name FROM imports")}

    def delete_imports(self, ids: Iterable) -> None:
        with self.conn:
            self.conn.executemany("DELETE FROM imports WHERE id = ?",
                                  [(i,) for i in ids])
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # ------------------------------------------------------------ entries
    def load_entries(self, import_ids: Iterable) -> list:
        ids = list(import_ids)
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        cur = self.conn.execute(
            "SELECT id, import_id, line_no, ts, category, event, level,"
            " thread, player, players, extra, message FROM entries"
            f" WHERE import_id IN ({marks}) ORDER BY ts, import_id, line_no",
            ids)
        fromiso = datetime.fromisoformat
        out = []
        append = out.append
        for (eid, iid, ln, ts, cat, ev, lvl, thr, pl, pls, ex, msg) in cur:
            append(Entry(ts=fromiso(ts), category=cat, event=ev, level=lvl,
                         thread=thr, player=pl,
                         players=tuple(pls.split(",")) if pls else (),
                         message=msg, extra=ex, line_no=ln, import_id=iid,
                         id=eid))
        return out
