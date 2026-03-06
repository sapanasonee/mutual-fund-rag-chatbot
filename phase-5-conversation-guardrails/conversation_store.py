from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StoredMessage:
    role: str  # "user" | "assistant"
    content: str
    created_at: str


class ConversationStore:
    """
    Minimal conversation store backed by SQLite (stdlib).

    Stores:
    - conversation id
    - message history
    - last referenced scheme_id (for follow-up pronoun resolution)
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                  conversation_id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  conversation_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_state (
                  conversation_id TEXT PRIMARY KEY,
                  last_scheme_id TEXT,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
                )
                """
            )

    def create_conversation(self) -> str:
        conversation_id = str(uuid.uuid4())
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations(conversation_id, created_at, updated_at) VALUES (?, ?, ?)",
                (conversation_id, now, now),
            )
            conn.execute(
                "INSERT OR REPLACE INTO conversation_state(conversation_id, last_scheme_id, updated_at) VALUES (?, ?, ?)",
                (conversation_id, None, now),
            )
        return conversation_id

    def touch(self, conversation_id: str) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations(conversation_id, created_at, updated_at) VALUES (?, ?, ?)",
                (conversation_id, now, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE conversation_id=?",
                (now, conversation_id),
            )
            conn.execute(
                "INSERT OR IGNORE INTO conversation_state(conversation_id, last_scheme_id, updated_at) VALUES (?, ?, ?)",
                (conversation_id, None, now),
            )

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        self.touch(conversation_id)
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE conversation_id=?",
                (now, conversation_id),
            )

    def get_recent_messages(self, conversation_id: str, limit: int = 10) -> list[StoredMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        msgs = [StoredMessage(role=r[0], content=r[1], created_at=r[2]) for r in rows]
        msgs.reverse()
        return msgs

    def set_last_scheme_id(self, conversation_id: str, scheme_id: Optional[str]) -> None:
        self.touch(conversation_id)
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO conversation_state(conversation_id, last_scheme_id, updated_at) VALUES (?, ?, ?)",
                (conversation_id, scheme_id, now),
            )

    def get_last_scheme_id(self, conversation_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_scheme_id FROM conversation_state WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        if not row:
            return None
        return row[0]

