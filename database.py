"""SQLite sxema va CRUD funksiyalari.

Jadvallar:
  * words    — parse_pdf.py orqali to'ldiriladi (mavzu, arabcha_soz, ozbekcha_tarjima)
  * users    — Telegram foydalanuvchilari
  * progress — har bir (foydalanuvchi, so'z) juftligi uchun holat ("known"/"unknown")
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "words.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id                INTEGER PRIMARY KEY,
    mavzu             TEXT NOT NULL,
    arabcha_soz       TEXT NOT NULL,
    ozbekcha_tarjima  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progress (
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    word_id     INTEGER NOT NULL REFERENCES words(id),
    status      TEXT NOT NULL CHECK (status IN ('known', 'unknown')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, word_id)
);
"""


def get_connection(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or DEFAULT_DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db(db_path: str | os.PathLike[str] | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------------- #
#  users
# --------------------------------------------------------------------------- #
def ensure_user(
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username, first_name = excluded.first_name
            """,
            (user_id, username, first_name),
        )


# --------------------------------------------------------------------------- #
#  words / mavzular
# --------------------------------------------------------------------------- #
def get_categories(db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Mavzular ro'yxati, kitobdagi tartibda (birinchi so'z id'siga ko'ra)."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT mavzu, COUNT(*) AS cnt, MIN(id) AS first_id
            FROM words
            GROUP BY mavzu
            ORDER BY first_id
            """
        ).fetchall()
    return [{"mavzu": r["mavzu"], "count": r["cnt"]} for r in rows]


def get_words_by_category(
    mavzu: str, db_path: str | os.PathLike[str] | None = None
) -> list[dict[str, Any]]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM words WHERE mavzu = ? ORDER BY id", (mavzu,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_word(word_id: int, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
    return dict(row) if row else None


def count_words(db_path: str | os.PathLike[str] | None = None) -> int:
    with get_connection(db_path) as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM words").fetchone()
    return count


# --------------------------------------------------------------------------- #
#  progress
# --------------------------------------------------------------------------- #
def set_status(
    user_id: int,
    word_id: int,
    status: str,
    db_path: str | os.PathLike[str] | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO progress (user_id, word_id, status, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, word_id) DO UPDATE SET
                status = excluded.status, updated_at = excluded.updated_at
            """,
            (user_id, word_id, status),
        )


def get_stats(user_id: int, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    with get_connection(db_path) as conn:
        total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]

        agg = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'known' THEN 1 ELSE 0 END) AS known,
                SUM(CASE WHEN status = 'unknown' THEN 1 ELSE 0 END) AS unknown
            FROM progress WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        known = agg["known"] or 0
        unknown = agg["unknown"] or 0
        started = known + unknown

        by_category = conn.execute(
            """
            SELECT w.mavzu AS mavzu,
                   COUNT(w.id) AS total,
                   SUM(CASE WHEN p.status = 'known' THEN 1 ELSE 0 END) AS known
            FROM words w
            LEFT JOIN progress p ON p.word_id = w.id AND p.user_id = ?
            GROUP BY w.mavzu
            ORDER BY MIN(w.id)
            """,
            (user_id,),
        ).fetchall()

    return {
        "total_words": total_words,
        "known": known,
        "unknown": unknown,
        "not_started": total_words - started,
        "by_category": [
            {"mavzu": r["mavzu"], "total": r["total"], "known": r["known"] or 0}
            for r in by_category
        ],
    }


if __name__ == "__main__":
    init_db()
    print(f"Baza tayyor: {DEFAULT_DB_PATH}")
    print(f"So'zlar soni: {count_words()}")
    print(f"Mavzular soni: {len(get_categories())}")
