"""SQLite connection and schema initialisation."""
from __future__ import annotations

import os
import sqlite3
from importlib import resources
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "agesdk.sqlite"
SCHEMA_VERSION = 5


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


# Tables safe to rebuild during a schema upgrade: never the raw layer, and
# reference tables that are reloaded from data/reference/ anyway.
# History is never rebuilt: the raw layer, its fetch log, and snapshot history.
PRESERVED_TABLES = {"raw_response", "fetch_log", "snapshot_run", "snapshot_membership"}
RELOADABLE_TABLES = {"species_taxon", "analysis_threshold"}


class MigrationError(RuntimeError):
    pass


def _upgrade(conn: sqlite3.Connection, from_version: int) -> None:
    """Pre-release upgrade: rebuild every non-raw table, but only if it holds no
    derived data. Refuses rather than discarding anything that isn't reloadable."""
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    to_drop = [t for t in tables if t not in PRESERVED_TABLES]
    occupied = [t for t in to_drop if t not in RELOADABLE_TABLES
                and conn.execute(f'SELECT EXISTS (SELECT 1 FROM "{t}")').fetchone()[0]]
    if occupied:
        raise MigrationError(
            f"schema v{from_version} -> v{SCHEMA_VERSION} needs to rebuild tables that hold data: "
            f"{occupied}. Write an explicit migration.")
    conn.execute("PRAGMA foreign_keys = OFF")
    for v in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'")]:
        conn.execute(f'DROP VIEW "{v}"')
    for t in to_drop:
        conn.execute(f'DROP TABLE "{t}"')
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def init_db(conn: sqlite3.Connection) -> None:
    """Create or refresh the schema. Idempotent; upgrades empty pre-release schemas."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if 0 < current < SCHEMA_VERSION:
        _upgrade(conn, current)
    sql = resources.files("agesdk").joinpath("schema.sql").read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()
