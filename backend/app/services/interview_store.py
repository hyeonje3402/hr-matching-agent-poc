import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).resolve().parents[2] / "interviews.sqlite3"


class InterviewStore:
    """Small local SQLite store for recoverable interview sessions and history."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS interviews (
                    session_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    position TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _connection(self):
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save(self, session: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(session, ensure_ascii=False)
        with self._connection() as db:
            db.execute(
                """INSERT INTO interviews
                (session_id, company_name, position, status, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                  company_name=excluded.company_name, position=excluded.position,
                  status=excluded.status, updated_at=excluded.updated_at, payload=excluded.payload""",
                (session["session_id"], session["company_name"], session["position"],
                 session["status"], session["created_at"], session["updated_at"], payload),
            )
        return session

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as db:
            row = db.execute("SELECT payload FROM interviews WHERE session_id=?", (session_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT payload FROM interviews ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def delete(self, session_id: str) -> bool:
        with self._connection() as db:
            cursor = db.execute("DELETE FROM interviews WHERE session_id=?", (session_id,))
        return cursor.rowcount > 0
