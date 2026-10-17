"""שמירת שיחות ושאלות לנציג ב-SQLite (data/app.db) — שורד רענון וגם הפעלה מחדש של השרת.

כל רשומה נשמרת כ-JSON של מודל Pydantic. פשוט, ומספיק לפיילוט של עשרות שיחות במקביל.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.contracts import ConversationState, OptionRequest, RepQuestion, Tracked
from app.seed import ROOT

DB_PATH = ROOT / "data" / "app.db"


class ConversationRecord(BaseModel):
    """מה שנשמר לכל שיחה. state הוא מה שהממשק רואה; השאר — זיכרון פנימי של הסוכן."""

    state: ConversationState
    history: list[dict] = Field(default_factory=list)  # ההיסטוריה של Gemini, כולל קריאות לכלים
    alternatives: list[OptionRequest] = Field(default_factory=list)  # החלופות בהשוואה האחרונה
    participations: dict[str, Tracked[float]] = Field(default_factory=dict)  # car_id → השתתפות ידועה
    guard_events: list[dict] = Field(default_factory=list)  # מה ש-Number Guard חסם


class Store:
    def __init__(self, path: Path = DB_PATH):
        self._lock = threading.Lock()
        self._con = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._con.executescript(
            """
            PRAGMA journal_mode = WAL;      -- קוראים לא חוסמים כותבים
            PRAGMA busy_timeout = 5000;
            CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rep_questions (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_questions_status ON rep_questions (status, created_at);
            CREATE INDEX IF NOT EXISTS idx_questions_conversation ON rep_questions (conversation_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations (updated_at);
            """
        )

    def purge_older_than(self, days: int) -> int:
        """מחיקת שיחות (ושאלות הנציג שלהן) שלא עודכנו X ימים — נתוני שכר לא נשמרים לנצח."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock, self._con:
            old = [r[0] for r in self._con.execute("SELECT id FROM conversations WHERE updated_at < ?", (cutoff,))]
            self._con.executemany("DELETE FROM rep_questions WHERE conversation_id = ?", [(i,) for i in old])
            self._con.executemany("DELETE FROM conversations WHERE id = ?", [(i,) for i in old])
        return len(old)

    # ---------- שיחות ----------

    def get(self, conversation_id: str) -> ConversationRecord | None:
        row = self._con.execute("SELECT data FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        record = ConversationRecord.model_validate_json(row[0])
        record.state.pending_questions = self.questions(conversation_id=conversation_id, status="open")
        return record

    def save(self, record: ConversationRecord) -> None:
        record.state.pending_questions = self.questions(conversation_id=record.state.conversation_id, status="open")
        with self._lock, self._con:
            self._con.execute(
                "INSERT OR REPLACE INTO conversations VALUES (?, ?, ?)",
                (record.state.conversation_id, record.model_dump_json(), _now()),
            )

    # ---------- שאלות לנציג ----------

    def questions(self, conversation_id: str | None = None, status: str | None = None) -> list[RepQuestion]:
        sql, params = "SELECT data FROM rep_questions WHERE 1=1", []
        if conversation_id:
            sql += " AND conversation_id = ?"
            params.append(conversation_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        return [RepQuestion.model_validate_json(r[0]) for r in self._con.execute(sql, params)]

    def question(self, question_id: str) -> RepQuestion | None:
        row = self._con.execute("SELECT data FROM rep_questions WHERE id = ?", (question_id,)).fetchone()
        return RepQuestion.model_validate_json(row[0]) if row else None

    def save_question(self, q: RepQuestion) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT OR REPLACE INTO rep_questions VALUES (?, ?, ?, ?, ?)",
                (q.id, q.conversation_id, q.status, q.created_at.isoformat(), q.model_dump_json()),
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def use_store(store: Store) -> None:
    """לבדיקות: מחליף ל-DB זמני."""
    global _store
    _store = store
