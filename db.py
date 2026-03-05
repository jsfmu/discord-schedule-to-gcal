"""SQLite storage for tokens, dedupe, and pending approval state."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data.db"
logger = logging.getLogger(__name__)

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_schedules (
                message_id INTEGER PRIMARY KEY,
                shifts_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_approvals (
                user_id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL,
                shifts_json TEXT NOT NULL,
                state TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gcal_tokens (
                user_id INTEGER PRIMARY KEY,
                token_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    logger.info("DB initialized at %s", DB_PATH)

def is_processed(message_id: int, shifts_hash: str) -> bool:
    """Check if we already processed this message_id + shifts combo."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_schedules WHERE message_id = ? AND shifts_hash = ?",
            (message_id, shifts_hash),
        ).fetchone()
    return row is not None

def mark_processed(message_id: int, shifts_hash: str) -> None:
    """Record that we processed this schedule."""
    import datetime
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO processed_schedules (message_id, shifts_hash, created_at) VALUES (?, ?, ?)",
            (message_id, shifts_hash, datetime.datetime.utcnow().isoformat()),
        )

def set_pending(user_id: int, message_id: int, shifts_json: str, state: str) -> None:
    """Store or update pending approval state."""
    import datetime
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pending_approvals (user_id, message_id, shifts_json, state, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, message_id, shifts_json, state, datetime.datetime.utcnow().isoformat()),
        )
    logger.info("Set pending: user=%s msg=%s state=%s", user_id, message_id, state)

def get_pending(user_id: int) -> Optional[dict]:
    """Get pending approval for user. Returns dict with message_id, shifts_json, state or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT message_id, shifts_json, state FROM pending_approvals WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {"message_id": row["message_id"], "shifts_json": row["shifts_json"], "state": row["state"]}

def clear_pending(user_id: int) -> None:
    """Clear pending approval for user."""
    with get_conn() as conn:
        conn.execute("DELETE FROM pending_approvals WHERE user_id = ?", (user_id,))
    logger.info("Cleared pending for user %s", user_id)

def save_gcal_token(user_id: int, token_json: str) -> None:
    """Save Google Calendar OAuth token for user."""
    import datetime
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO gcal_tokens (user_id, token_json, updated_at) VALUES (?, ?, ?)""",
            (user_id, token_json, datetime.datetime.utcnow().isoformat()),
        )

def load_gcal_token(user_id: int) -> Optional[str]:
    """Load Google Calendar OAuth token for user, or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT token_json FROM gcal_tokens WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row["token_json"] if row else None
