import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "medipilot.db"


def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database():
    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                clinical_summary TEXT
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES sessions(session_id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                doctor_id INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES sessions(session_id)
            )
        """)


def create_session():
    session_id = str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions(session_id, created_at)
            VALUES (?, ?)
            """,
            (
                session_id,
                datetime.now(timezone.utc).isoformat()
            )
        )

    return session_id


def session_exists(session_id):
    with get_connection() as connection:
        result = connection.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()

    return result is not None


def save_message(session_id, role, content):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO messages
            (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                datetime.now(timezone.utc).isoformat()
            )
        )


def get_session(session_id):
    with get_connection() as connection:

        session = connection.execute(
            """
            SELECT * FROM sessions
            WHERE session_id = ?
            """,
            (session_id,)
        ).fetchone()

        if session is None:
            return None

        messages = connection.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,)
        ).fetchall()

    return {
        "session_id": session_id,
        "messages": [dict(message) for message in messages],
        "clinical_summary": session["clinical_summary"]
    }


def save_appointment(
    session_id,
    doctor_id,
    appointment_date,
    appointment_time
):
    appointment_id = str(uuid.uuid4())

    with get_connection() as connection:

        connection.execute(
            """
            INSERT INTO appointments
            (
                appointment_id,
                session_id,
                doctor_id,
                appointment_date,
                appointment_time,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                appointment_id,
                session_id,
                doctor_id,
                str(appointment_date),
                str(appointment_time),
                "demo_confirmed"
            )
        )

    return appointment_id
