"""שמירת שיחות ושאלות לנציג ב-SQLite (data/app.db) — שורד רענון וגם הפעלה מחדש של השרת.

כל רשומה נשמרת כ-JSON של מודל Pydantic. פשוט, ומספיק לפיילוט של עשרות שיחות במקביל.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.contracts import ConversationState, EmployeeProfile, OptionRequest, RepQuestion, Tracked
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
            CREATE TABLE IF NOT EXISTS employee_profiles (
                owner_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rep_questions (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee',
                full_name TEXT, mobile_number TEXT, password_setup_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS employee_setup_attempts (
                email TEXT NOT NULL, client_ip TEXT NOT NULL,
                attempts INTEGER NOT NULL, window_started_at REAL NOT NULL,
                PRIMARY KEY (email, client_ip)
            );
            CREATE TABLE IF NOT EXISTS representative_activation_codes (
                code_hash TEXT PRIMARY KEY, email TEXT NOT NULL COLLATE NOCASE,
                expires_at TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_questions_status ON rep_questions (status, created_at);
            CREATE INDEX IF NOT EXISTS idx_questions_conversation ON rep_questions (conversation_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations (updated_at);
            """
        )
        columns = {row[1] for row in self._con.execute("PRAGMA table_info(conversations)")}
        if "owner_id" not in columns:
            self._con.execute("ALTER TABLE conversations ADD COLUMN owner_id TEXT")
        self._con.execute("CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations (owner_id)")
        user_columns = {row[1] for row in self._con.execute("PRAGMA table_info(users)")}
        if "role" not in user_columns:
            self._con.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'employee'")
        if "full_name" not in user_columns:
            self._con.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        if "mobile_number" not in user_columns:
            self._con.execute("ALTER TABLE users ADD COLUMN mobile_number TEXT")
        if "password_setup_hash" not in user_columns:
            self._con.execute("ALTER TABLE users ADD COLUMN password_setup_hash TEXT")
        question_columns = {row[1] for row in self._con.execute("PRAGMA table_info(rep_questions)")}
        if "answered_by" not in question_columns:
            self._con.execute("ALTER TABLE rep_questions ADD COLUMN answered_by TEXT")

    def purge_older_than(self, days: int) -> int:
        """מחיקת שיחות (ושאלות הנציג שלהן) שלא עודכנו X ימים — נתוני שכר לא נשמרים לנצח."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock, self._con:
            old = [r[0] for r in self._con.execute("SELECT id FROM conversations WHERE updated_at < ?", (cutoff,))]
            self._con.executemany("DELETE FROM rep_questions WHERE conversation_id = ?", [(i,) for i in old])
            self._con.executemany("DELETE FROM conversations WHERE id = ?", [(i,) for i in old])
            self._con.execute("DELETE FROM employee_profiles WHERE updated_at < ?", (cutoff,))
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
        updated_at = _now()
        with self._lock, self._con:
            owner = self._con.execute(
                "SELECT owner_id FROM conversations WHERE id = ?",
                (record.state.conversation_id,),
            ).fetchone()
            self._con.execute(
                """INSERT INTO conversations (id, data, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
                (record.state.conversation_id, record.model_dump_json(), updated_at),
            )
            if owner is not None and owner[0] is not None:
                self._con.execute(
                    """INSERT INTO employee_profiles (owner_id, data, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(owner_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
                    (owner[0], record.state.profile.model_dump_json(), updated_at),
                )

    def save_owned(self, record: ConversationRecord, owner_id: str) -> None:
        record.state.pending_questions = self.questions(conversation_id=record.state.conversation_id, status="open")
        updated_at = _now()
        with self._lock, self._con:
            row = self._con.execute(
                "SELECT owner_id FROM conversations WHERE id = ?",
                (record.state.conversation_id,),
            ).fetchone()
            if row is not None and row[0] != owner_id:
                raise ValueError("Conversation belongs to another user")
            self._con.execute(
                """INSERT INTO conversations (id, data, updated_at, owner_id) VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data = excluded.data,
                    updated_at = excluded.updated_at, owner_id = excluded.owner_id""",
                (record.state.conversation_id, record.model_dump_json(), updated_at, owner_id),
            )
            self._con.execute(
                """INSERT INTO employee_profiles (owner_id, data, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(owner_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
                (owner_id, record.state.profile.model_dump_json(), updated_at),
            )

    def get_profile(self, owner_id: str) -> EmployeeProfile | None:
        row = self._con.execute(
            "SELECT data FROM employee_profiles WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()
        if row is None:
            # Adopt profiles from conversations saved before cross-conversation persistence was added.
            row = self._con.execute(
                "SELECT data FROM conversations WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 1",
                (owner_id,),
            ).fetchone()
            if row is None:
                return None
            return ConversationRecord.model_validate_json(row[0]).state.profile
        return EmployeeProfile.model_validate_json(row[0])

    def get_owned(self, conversation_id: str, owner_id: str) -> ConversationRecord | None:
        row = self._con.execute(
            "SELECT data FROM conversations WHERE id = ? AND owner_id = ?",
            (conversation_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        record = ConversationRecord.model_validate_json(row[0])
        record.state.pending_questions = self.questions(conversation_id=conversation_id, status="open")
        return record

    def create_user(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        full_name: str | None = None,
        mobile_number: str | None = None,
    ) -> bool:
        return self.create_account(
            user_id, email, password_hash, "employee", full_name, mobile_number,
        )

    def create_account(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        role: str,
        full_name: str | None = None,
        mobile_number: str | None = None,
    ) -> bool:
        if role not in {"employee", "rep"}:
            raise ValueError("Public account creation is limited to employee and representative roles.")
        try:
            with self._lock, self._con:
                self._con.execute(
                    """INSERT INTO users
                    (id, email, password_hash, created_at, role, full_name, mobile_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, email, password_hash, _now(), role, full_name, mobile_number),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def create_representative_activation(self, email: str, code_hash: str, expires_at: str) -> None:
        with self._lock, self._con:
            self._con.execute(
                """DELETE FROM representative_activation_codes
                WHERE email = ? COLLATE NOCASE""",
                (email,),
            )
            self._con.execute(
                """INSERT INTO representative_activation_codes
                (code_hash, email, expires_at, created_at) VALUES (?, ?, ?, ?)""",
                (code_hash, email, expires_at, _now()),
            )

    def representative_activation_valid(self, email: str, code_hash: str) -> bool:
        row = self._con.execute(
            """SELECT email, expires_at FROM representative_activation_codes
            WHERE code_hash = ?""",
            (code_hash,),
        ).fetchone()
        return bool(
            row
            and row[0].lower() == email.lower()
            and row[1] > _now()
        )

    def activate_representative(
        self,
        user_id: str,
        email: str,
        password_hash: str,
        code_hash: str,
    ) -> str:
        now = _now()
        with self._lock, self._con:
            activation = self._con.execute(
                """SELECT email, expires_at FROM representative_activation_codes
                WHERE code_hash = ?""",
                (code_hash,),
            ).fetchone()
            if activation is None or activation[0].lower() != email.lower() or activation[1] <= now:
                if activation is not None and activation[1] <= now:
                    self._con.execute(
                        "DELETE FROM representative_activation_codes WHERE code_hash = ?",
                        (code_hash,),
                    )
                return "invalid"
            if self._con.execute(
                "SELECT 1 FROM users WHERE email = ? COLLATE NOCASE",
                (email,),
            ).fetchone():
                return "exists"
            try:
                self._con.execute(
                    """INSERT INTO users
                    (id, email, password_hash, created_at, role)
                    VALUES (?, ?, ?, ?, 'rep')""",
                    (user_id, email, password_hash, now),
                )
            except sqlite3.IntegrityError:
                return "exists"
            self._con.execute(
                "DELETE FROM representative_activation_codes WHERE code_hash = ?",
                (code_hash,),
            )
            return "created"

    def create_pending_employee(
        self,
        user_id: str,
        email: str,
        setup_code_hash: str,
        full_name: str | None = None,
        mobile_number: str | None = None,
    ) -> bool:
        try:
            with self._lock, self._con:
                self._con.execute(
                    """INSERT INTO users
                    (id, email, password_hash, created_at, role, full_name, mobile_number, password_setup_hash)
                    VALUES (?, ?, 'pending', ?, 'employee', ?, ?, ?)""",
                    (user_id, email, _now(), full_name, mobile_number, setup_code_hash),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def reissue_employee_setup_code(self, email: str, setup_code_hash: str) -> bool:
        with self._lock, self._con:
            cursor = self._con.execute(
                """UPDATE users SET password_setup_hash = ?
                WHERE email = ? COLLATE NOCASE AND role = 'employee'
                    AND password_hash = 'pending'""",
                (setup_code_hash, email),
            )
            if cursor.rowcount:
                self._con.execute(
                    "DELETE FROM employee_setup_attempts WHERE email = ? COLLATE NOCASE",
                    (email,),
                )
            return cursor.rowcount == 1

    def set_employee_password(self, email: str, setup_code_hash: str, password_hash: str) -> str | None:
        with self._lock, self._con:
            row = self._con.execute(
                """SELECT id FROM users
                WHERE email = ? COLLATE NOCASE AND role = 'employee'
                    AND password_setup_hash = ? AND password_hash = 'pending'""",
                (email, setup_code_hash),
            ).fetchone()
            if row is None:
                return None
            self._con.execute(
                """UPDATE users SET password_hash = ?, password_setup_hash = NULL
                WHERE id = ?""",
                (password_hash, row[0]),
            )
            return row[0]

    def employee_setup_valid(self, email: str, setup_code_hash: str) -> bool:
        row = self._con.execute(
            """SELECT 1 FROM users
            WHERE email = ? COLLATE NOCASE AND role = 'employee'
                AND password_setup_hash = ? AND password_hash = 'pending'""",
            (email, setup_code_hash),
        ).fetchone()
        return row is not None

    def employee_setup_attempt_allowed(
        self,
        email: str,
        client_ip: str,
        max_attempts: int = 10,
        window_seconds: int = 900,
    ) -> bool:
        now = time.time()
        with self._lock, self._con:
            self._con.execute(
                "DELETE FROM employee_setup_attempts WHERE window_started_at <= ?",
                (now - window_seconds,),
            )
            row = self._con.execute(
                """SELECT attempts, window_started_at FROM employee_setup_attempts
                WHERE email = ? COLLATE NOCASE AND client_ip = ?""",
                (email, client_ip),
            ).fetchone()
            if row is None:
                return True
            return row[0] < max_attempts

    def record_employee_setup_failure(
        self,
        email: str,
        client_ip: str,
        window_seconds: int = 900,
    ) -> None:
        now = time.time()
        with self._lock, self._con:
            self._con.execute(
                "DELETE FROM employee_setup_attempts WHERE window_started_at <= ?",
                (now - window_seconds,),
            )
            pending = self._con.execute(
                """SELECT 1 FROM users WHERE email = ? COLLATE NOCASE
                AND role = 'employee' AND password_hash = 'pending'""",
                (email,),
            ).fetchone()
            if pending is None:
                return
            row = self._con.execute(
                """SELECT attempts, window_started_at FROM employee_setup_attempts
                WHERE email = ? COLLATE NOCASE AND client_ip = ?""",
                (email, client_ip),
            ).fetchone()
            if row is None or now - row[1] >= window_seconds:
                self._con.execute(
                    """INSERT INTO employee_setup_attempts
                    (email, client_ip, attempts, window_started_at) VALUES (?, ?, 1, ?)
                    ON CONFLICT(email, client_ip) DO UPDATE SET
                    attempts = 1, window_started_at = excluded.window_started_at""",
                    (email, client_ip, now),
                )
            else:
                self._con.execute(
                    """UPDATE employee_setup_attempts SET attempts = attempts + 1
                    WHERE email = ? COLLATE NOCASE AND client_ip = ?""",
                    (email, client_ip),
                )

    def clear_employee_setup_attempts(self, email: str, client_ip: str) -> None:
        with self._lock, self._con:
            self._con.execute(
                """DELETE FROM employee_setup_attempts
                WHERE email = ? COLLATE NOCASE AND client_ip = ?""",
                (email, client_ip),
            )

    def upsert_admin_account(self, email: str, password_hash: str) -> bool:
        try:
            with self._lock, self._con:
                self._con.execute(
                    """INSERT INTO users
                    (id, email, password_hash, created_at, role)
                    VALUES ('system-admin', ?, ?, ?, 'admin')
                    ON CONFLICT(id) DO UPDATE SET
                        email = excluded.email, password_hash = excluded.password_hash, role = 'admin'""",
                    (email, password_hash, _now()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def user_by_email(self, email: str) -> dict | None:
        row = self._con.execute(
            """SELECT id, email, password_hash, role, full_name, mobile_number, password_setup_hash
            FROM users WHERE email = ? COLLATE NOCASE""",
            (email,),
        ).fetchone()
        return {
            "id": row[0], "email": row[1], "password_hash": row[2], "role": row[3],
            "full_name": row[4], "mobile_number": row[5], "password_setup_hash": row[6],
        } if row else None

    def create_session(self, token_hash: str, user_id: str, expires_at: str) -> None:
        with self._lock, self._con:
            self._con.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (_now(),))
            self._con.execute(
                "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (token_hash, user_id, expires_at),
            )

    def session_user(self, token_hash: str) -> dict | None:
        row = self._con.execute(
            """SELECT users.id, users.email, users.role, users.full_name, users.mobile_number
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?""",
            (token_hash, _now()),
        ).fetchone()
        return {
            "id": row[0], "email": row[1], "role": row[2],
            "full_name": row[3], "mobile_number": row[4],
        } if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._lock, self._con:
            self._con.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))

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
                """INSERT INTO rep_questions (id, conversation_id, status, created_at, data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET status = excluded.status, data = excluded.data""",
                (q.id, q.conversation_id, q.status, q.created_at.isoformat(), q.model_dump_json()),
            )

    def answer_question(self, q: RepQuestion, representative_id: str) -> bool:
        with self._lock, self._con:
            cursor = self._con.execute(
                """UPDATE rep_questions SET status = ?, data = ?, answered_by = ?
                WHERE id = ? AND status = 'open' AND answered_by IS NULL""",
                (q.status, q.model_dump_json(), representative_id, q.id),
            )
            return cursor.rowcount == 1

    def questions_for_representative(self, representative_id: str, status: str | None = None) -> list[RepQuestion]:
        query = """SELECT data FROM rep_questions
            WHERE (status = 'open' OR answered_by = ?)"""
        params: list[str] = [representative_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = self._con.execute(
            query, params,
        )
        return [RepQuestion.model_validate_json(row[0]) for row in rows]


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
