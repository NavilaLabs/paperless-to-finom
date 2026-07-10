"""SQLite audit log of everything sent to Finom."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sent_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paperless_id    INTEGER NOT NULL,
    title           TEXT,
    filename        TEXT NOT NULL,
    finom_email     TEXT NOT NULL,
    status          TEXT NOT NULL,          -- 'sent' | 'error' | 'skipped'
    error           TEXT,
    sent_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sent_paperless_id ON sent_documents(paperless_id);
CREATE INDEX IF NOT EXISTS idx_sent_status ON sent_documents(status);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def already_sent(self, paperless_id: int) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM sent_documents WHERE paperless_id=? AND status='sent' LIMIT 1",
            (paperless_id,),
        )
        return cur.fetchone() is not None

    def record(
        self,
        *,
        paperless_id: int,
        title: str | None,
        filename: str,
        finom_email: str,
        status: str,
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO sent_documents
               (paperless_id, title, filename, finom_email, status, error, sent_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                paperless_id,
                title,
                filename,
                finom_email,
                status,
                error,
                datetime.now(UTC).isoformat(),
            ),
        )
        self.conn.commit()

    def recent(self, limit: int = 20) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT * FROM sent_documents ORDER BY id DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()

    def close(self) -> None:
        self.conn.close()
