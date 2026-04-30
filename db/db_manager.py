import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).resolve().parent / "events.db"),
)


class DBManager:
    """SQLite-backed event storage manager."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self.init_db()

    def _connect(self):
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def init_db(self):
        assert self._conn is not None
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    device_id TEXT,
                    user_id TEXT,
                    event_type TEXT,
                    severity TEXT,
                    event_timestamp TEXT,
                    delirium_suspected INTEGER,
                    abnormal_exit INTEGER,
                    door_open INTEGER,
                    rfid_detected INTEGER,
                    buzzer_activated INTEGER,
                    heart_rate REAL,
                    sleep_state TEXT,
                    activity_level REAL,
                    door_distance_cm REAL,
                    raw_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(event_timestamp)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )
            self._conn.commit()

    def save_event(self, payload: dict[str, Any]) -> int:
        """Insert or replace an event payload and return the row id."""
        assert self._conn is not None

        processed = payload.get("processedSensorData", {}) or {}
        raw_payload = json.dumps(payload, ensure_ascii=False)

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO events (
                    event_id,
                    device_id,
                    user_id,
                    event_type,
                    severity,
                    event_timestamp,
                    delirium_suspected,
                    abnormal_exit,
                    door_open,
                    rfid_detected,
                    buzzer_activated,
                    heart_rate,
                    sleep_state,
                    activity_level,
                    door_distance_cm,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    device_id=excluded.device_id,
                    user_id=excluded.user_id,
                    event_type=excluded.event_type,
                    severity=excluded.severity,
                    event_timestamp=excluded.event_timestamp,
                    delirium_suspected=excluded.delirium_suspected,
                    abnormal_exit=excluded.abnormal_exit,
                    door_open=excluded.door_open,
                    rfid_detected=excluded.rfid_detected,
                    buzzer_activated=excluded.buzzer_activated,
                    heart_rate=excluded.heart_rate,
                    sleep_state=excluded.sleep_state,
                    activity_level=excluded.activity_level,
                    door_distance_cm=excluded.door_distance_cm,
                    raw_payload=excluded.raw_payload
                """,
                (
                    payload.get("eventId"),
                    payload.get("deviceId"),
                    payload.get("userId"),
                    payload.get("eventType"),
                    payload.get("severity"),
                    payload.get("timestamp"),
                    _to_int_bool(payload.get("deliriumSuspected")),
                    _to_int_bool(payload.get("abnormalExit")),
                    _to_int_bool(payload.get("doorOpen")),
                    _to_int_bool(payload.get("rfidDetected")),
                    _to_int_bool(payload.get("buzzerActivated")),
                    processed.get("heartRate"),
                    processed.get("sleepState"),
                    processed.get("activityLevel"),
                    processed.get("doorDistanceCm"),
                    raw_payload,
                ),
            )
            self._conn.commit()
            row_id = int(cursor.lastrowid or 0)

        logger.info("[DB] 이벤트 저장 | event_id=%s", payload.get("eventId"))
        return row_id

    def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return self._row_to_dict(row)

    def list_events(self, limit: int = 100, event_type: Optional[str] = None) -> list[dict[str, Any]]:
        assert self._conn is not None
        limit = max(1, int(limit))

        if event_type:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                WHERE event_type = ?
                ORDER BY event_timestamp DESC, id DESC
                LIMIT ?
                """,
                (event_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                ORDER BY event_timestamp DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_dict(row) for row in rows if row is not None]

    def delete_event(self, event_id: str) -> bool:
        assert self._conn is not None
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM events WHERE event_id = ?",
                (event_id,),
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def close(self):
        if self._conn is None:
            return
        self._conn.close()
        self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @staticmethod
    def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
        if row is None:
            return None

        data = dict(row)
        raw_payload = data.get("raw_payload")
        if raw_payload:
            try:
                data["payload"] = json.loads(raw_payload)
            except json.JSONDecodeError:
                data["payload"] = raw_payload
        return data


def _to_int_bool(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(bool(value))
