import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.services.interview_store import DB_PATH


class MaterialStore:
    """Additive SQLite storage for reusable local job and applicant source material."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        with self._connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS preparation_materials (
                material_id TEXT PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL,
                title TEXT NOT NULL, company_name TEXT NOT NULL DEFAULT '',
                position TEXT NOT NULL DEFAULT '', source_url TEXT,
                content_hash TEXT NOT NULL, raw_text TEXT NOT NULL,
                analysis_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_material_hash ON preparation_materials(kind, content_hash)")

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

    @staticmethod
    def digest(kind: str, content: bytes | str) -> str:
        value = content.encode("utf-8") if isinstance(content, str) else content
        return sha256(kind.encode("utf-8") + b"\0" + value).hexdigest()

    @staticmethod
    def _decode(row):
        if not row:
            return None
        value = dict(row)
        value["analysis"] = json.loads(value.pop("analysis_json"))
        return value

    def find_by_hash(self, kind: str, content_hash: str) -> Optional[dict[str, Any]]:
        with self._connection() as db:
            row = db.execute("SELECT * FROM preparation_materials WHERE kind=? AND content_hash=? ORDER BY created_at DESC LIMIT 1", (kind, content_hash)).fetchone()
        return self._decode(row)

    def save(self, *, kind: str, source: str, title: str, raw_text: str,
             analysis: dict, company_name: str = "", position: str = "",
             source_url: Optional[str] = None, content_hash: Optional[str] = None) -> dict:
        digest = content_hash or self.digest(kind, raw_text)
        existing = self.find_by_hash(kind, digest)
        if existing:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "material_id": str(uuid4()), "kind": kind, "source": source, "title": title[:240],
            "company_name": company_name[:120], "position": position[:160], "source_url": source_url,
            "content_hash": digest, "raw_text": raw_text[:30000], "analysis": analysis,
            "created_at": now, "updated_at": now,
        }
        with self._connection() as db:
            db.execute("""INSERT INTO preparation_materials
              (material_id, kind, source, title, company_name, position, source_url, content_hash, raw_text, analysis_json, created_at, updated_at)
              VALUES (:material_id,:kind,:source,:title,:company_name,:position,:source_url,:content_hash,:raw_text,:analysis,:created_at,:updated_at)""",
              {**item, "analysis": json.dumps(analysis, ensure_ascii=False)})
        return item

    def get(self, material_id: str) -> Optional[dict[str, Any]]:
        with self._connection() as db:
            row = db.execute("SELECT * FROM preparation_materials WHERE material_id=?", (material_id,)).fetchone()
        return self._decode(row)

    def list(self, kind: Optional[str] = None) -> list[dict[str, Any]]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM preparation_materials WHERE (? IS NULL OR kind=?) ORDER BY updated_at DESC LIMIT 200", (kind, kind)).fetchall()
        return [self._decode(row) for row in rows]

    def save_fit(self, material_id: str, resume_hash: str, fit: dict) -> None:
        with self._connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requirement_fits (
                material_id TEXT NOT NULL, resume_hash TEXT NOT NULL, fit_json TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY(material_id, resume_hash)
            )""")
            db.execute("""INSERT INTO requirement_fits(material_id,resume_hash,fit_json,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(material_id,resume_hash) DO UPDATE SET
                fit_json=excluded.fit_json, updated_at=excluded.updated_at""",
                (material_id, resume_hash, json.dumps(fit, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))

    def get_fit(self, material_id: str, resume_hash: str) -> Optional[dict]:
        with self._connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requirement_fits (
                material_id TEXT NOT NULL, resume_hash TEXT NOT NULL, fit_json TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY(material_id, resume_hash)
            )""")
            row = db.execute("SELECT fit_json FROM requirement_fits WHERE material_id=? AND resume_hash=?", (material_id, resume_hash)).fetchone()
        return json.loads(row["fit_json"]) if row else None

    def update_job(self, material_id: str, company_name: str, position: str, analysis: dict) -> Optional[dict]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as db:
            cursor = db.execute("UPDATE preparation_materials SET company_name=?, position=?, analysis_json=?, updated_at=? WHERE material_id=? AND kind='job'",
                                (company_name[:120], position[:160], json.dumps(analysis, ensure_ascii=False), now, material_id))
        return self.get(material_id) if cursor.rowcount else None
