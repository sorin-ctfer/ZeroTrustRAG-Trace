from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable

from .config import SQLITE_PATH, ensure_dirs
from .utils import utc8_now_iso


class EventLog:
    def __init__(self, db_path: Path | None = None):
        ensure_dirs()
        self.db_path = Path(db_path or SQLITE_PATH)
        self.init_db()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ref_id TEXT,
                    agent_id TEXT,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON event_log(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON event_log(agent_id)")

    def clear(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM event_log")

    def append(self, event_type: str, payload: Dict[str, Any], ref_id: str | None = None, agent_id: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO event_log(ts,event_type,ref_id,agent_id,payload) VALUES (?,?,?,?,?)",
                (utc8_now_iso(), event_type, ref_id, agent_id, json.dumps(payload, ensure_ascii=False)),
            )

    def extend(self, event_type: str, rows: Iterable[Dict[str, Any]], ref_key: str = "id", agent_key: str = "agent_id") -> None:
        for row in rows:
            self.append(event_type, row, row.get(ref_key), row.get(agent_key))

    def recent(self, limit: int = 200):
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id,ts,event_type,ref_id,agent_id,payload FROM event_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            try:
                item["payload"] = json.loads(item["payload"])
            except Exception:
                pass
            out.append(item)
        return list(reversed(out))
