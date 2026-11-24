import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from dashboard.database import connect, get_connection, initialize_schema


class ProbeError(Exception):
    pass


def build_app(database_path: Path, captured: list[sqlite3.Connection]) -> FastAPI:
    app = FastAPI()
    app.state.database_path = database_path

    @app.get("/count")
    def count(connection: Annotated[sqlite3.Connection, Depends(get_connection)]) -> dict[str, int]:
        captured.append(connection)
        row = connection.execute("SELECT COUNT(*) AS total FROM app_meta").fetchone()
        return {"total": row["total"]}

    @app.get("/boom")
    def boom(connection: Annotated[sqlite3.Connection, Depends(get_connection)]) -> dict[str, int]:
        captured.append(connection)
        raise ProbeError("route failed")

    return app


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "app.db"
    connection = connect(path)
    initialize_schema(connection)
    connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("k", "v"))
    connection.commit()
    connection.close()
    return path


@pytest.mark.acceptance
def test_dependency_provides_working_connection(database_path: Path) -> None:
    captured: list[sqlite3.Connection] = []
    client = TestClient(build_app(database_path, captured))
    response = client.get("/count")
    assert response.status_code == 200
    assert response.json() == {"total": 1}
    assert len(captured) == 1


@pytest.mark.acceptance
def test_connection_is_closed_after_request(database_path: Path) -> None:
    captured: list[sqlite3.Connection] = []
    client = TestClient(build_app(database_path, captured))
    client.get("/count")
    with pytest.raises(sqlite3.ProgrammingError):
        captured[0].execute("SELECT 1")


@pytest.mark.acceptance
def test_connection_is_closed_when_route_raises(database_path: Path) -> None:
    captured: list[sqlite3.Connection] = []
    client = TestClient(build_app(database_path, captured), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    assert len(captured) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        captured[0].execute("SELECT 1")


@pytest.mark.acceptance
def test_each_request_gets_its_own_connection(database_path: Path) -> None:
    captured: list[sqlite3.Connection] = []
    client = TestClient(build_app(database_path, captured))
    client.get("/count")
    client.get("/count")
    assert len(captured) == 2
    assert captured[0] is not captured[1]


@pytest.mark.acceptance
def test_connection_has_connect_settings(database_path: Path) -> None:
    app = FastAPI()
    app.state.database_path = database_path
    seen: dict[str, object] = {}

    @app.get("/pragmas")
    def pragmas(
        connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    ) -> dict[str, int]:
        seen["factory"] = connection.row_factory
        return {
            "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
            "busy_timeout": connection.execute("PRAGMA busy_timeout").fetchone()[0],
        }

    response = TestClient(app).get("/pragmas")
    assert response.json() == {"foreign_keys": 1, "busy_timeout": 5000}
    assert seen["factory"] is sqlite3.Row


@pytest.mark.acceptance
def test_dependency_follows_database_path_of_the_app(tmp_path: Path) -> None:
    first_path = tmp_path / "first.db"
    second_path = tmp_path / "second.db"
    for path, value in ((first_path, "one"), (second_path, "two")):
        connection = connect(path)
        initialize_schema(connection)
        connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("k", value))
        connection.commit()
        connection.close()

    def build(path: Path) -> FastAPI:
        app = FastAPI()
        app.state.database_path = path

        @app.get("/value")
        def value(
            connection: Annotated[sqlite3.Connection, Depends(get_connection)],
        ) -> dict[str, str]:
            return {"value": connection.execute("SELECT value FROM app_meta").fetchone()["value"]}

        return app

    assert TestClient(build(first_path)).get("/value").json() == {"value": "one"}
    assert TestClient(build(second_path)).get("/value").json() == {"value": "two"}


@pytest.mark.acceptance
def test_get_connection_is_a_generator_that_closes_on_exhaustion(database_path: Path) -> None:
    app = FastAPI()
    app.state.database_path = database_path
    request = Request({"type": "http", "app": app, "headers": [], "method": "GET", "path": "/"})
    generator: Iterator[sqlite3.Connection] = get_connection(request)
    connection = next(generator)
    assert connection.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(StopIteration):
        next(generator)
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
