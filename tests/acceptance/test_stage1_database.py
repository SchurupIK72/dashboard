import sqlite3
from pathlib import Path
from threading import Thread

import pytest

from dashboard import __version__
from dashboard.database import connect, initialize_schema


@pytest.mark.acceptance
def test_version_is_0_2_0() -> None:
    assert __version__ == "0.2.0"


@pytest.mark.acceptance
def test_connect_applies_pragmas(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        connection.close()


@pytest.mark.acceptance
def test_connect_creates_missing_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c" / "app.db"
    connection = connect(target)
    connection.close()
    assert target.parent.is_dir()
    assert target.is_file()


@pytest.mark.acceptance
def test_connect_returns_rows_addressable_by_name(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    try:
        row = connection.execute("SELECT 7 AS answer").fetchone()
        assert row["answer"] == 7
    finally:
        connection.close()


@pytest.mark.acceptance
def test_connection_is_usable_from_another_thread(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    outcome: list[int] = []

    def read_value() -> None:
        outcome.append(connection.execute("SELECT 1").fetchone()[0])

    worker = Thread(target=read_value)
    worker.start()
    worker.join(timeout=10)
    connection.close()
    assert outcome == [1]


@pytest.mark.acceptance
def test_initialize_schema_creates_app_meta(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    try:
        initialize_schema(connection)
        columns = {
            row["name"]: row for row in connection.execute("PRAGMA table_info(app_meta)").fetchall()
        }
        assert set(columns) == {"key", "value"}
        assert columns["key"]["pk"] == 1
        assert columns["value"]["notnull"] == 1
    finally:
        connection.close()


@pytest.mark.acceptance
def test_initialize_schema_twice_keeps_data(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    try:
        initialize_schema(connection)
        connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("k", "v"))
        connection.commit()
        initialize_schema(connection)
        rows = connection.execute("SELECT key, value FROM app_meta").fetchall()
        assert [(row["key"], row["value"]) for row in rows] == [("k", "v")]
    finally:
        connection.close()


@pytest.mark.acceptance
def test_data_persists_after_reopening_database(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    first = connect(path)
    initialize_schema(first)
    first.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("persist", "yes"))
    first.commit()
    first.close()
    second = connect(path)
    try:
        initialize_schema(second)
        row = second.execute("SELECT value FROM app_meta WHERE key = ?", ("persist",)).fetchone()
        assert row["value"] == "yes"
    finally:
        second.close()


@pytest.mark.acceptance
def test_app_meta_rejects_null_value_and_duplicate_key(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    try:
        initialize_schema(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("k", None))
        connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("k", "v"))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("k", "w"))
    finally:
        connection.close()


@pytest.mark.acceptance
def test_foreign_keys_are_enforced_on_connection(tmp_path: Path) -> None:
    connection = connect(tmp_path / "app.db")
    try:
        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO child (parent_id) VALUES (?)", (999,))
    finally:
        connection.close()
