import sqlite3
from importlib import resources
from pathlib import Path

BUSY_TIMEOUT_MS = 5000
SCHEMA_RESOURCE = "schema.sql"


def connect(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys, WAL and busy timeout enabled."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Apply the packaged schema.sql idempotently."""
    schema_sql = resources.files("dashboard").joinpath(SCHEMA_RESOURCE).read_text(encoding="utf-8")
    connection.executescript(schema_sql)
    connection.commit()
