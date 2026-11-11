"""SQLite connection and schema initialisation."""
from __future__ import annotations

import os
import sqlite3
from importlib import resources
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "agesdk.sqlite"
SCHEMA_VERSION = 1


def db_path() -> Path:
    return Path(os.environ.get("AGESDK_DB", DEFAULT_DB_PATH))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database. ``":memory:"`` is accepted for tests."""
    target = str(path) if path is not None else str(db_path())
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create or refresh the schema. Idempotent."""
    sql = resources.files("agesdk").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()
