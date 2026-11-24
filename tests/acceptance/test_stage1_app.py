import json
import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

import dashboard
from dashboard import main as main_module
from dashboard.main import create_app, templates
from dashboard.settings import Settings, load_settings

SECRET_KEY = "k9Zq-unit-secret-0123456789-abcdefXYZ"
USER_PASSWORDS = ("pw-alpha-7731", "pw-beta-4482", "pw-gamma-9915")
USERS = [
    {"login": "anna", "password": USER_PASSWORDS[0], "company": "Alpha"},
    {"login": "boris", "password": USER_PASSWORDS[1], "company": "Alpha"},
    {"login": "vera", "password": USER_PASSWORDS[2], "company": "Beta"},
]


def build_environ(database_path: Path) -> dict[str, str]:
    return {
        "SECRET_KEY": SECRET_KEY,
        "DASHBOARD_USERS": json.dumps(USERS),
        "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
    }


def build_settings(database_path: Path) -> Settings:
    return load_settings(environ=build_environ(database_path), env_file=None)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "dashboard.db"


@pytest.fixture
def settings(database_path: Path) -> Settings:
    return build_settings(database_path)


@pytest.mark.acceptance
def test_version_is_0_2_0() -> None:
    assert dashboard.__version__ == "0.2.0"


@pytest.mark.acceptance
def test_health_returns_ok_and_version(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": dashboard.__version__}
    assert response.json()["version"] == "0.2.0"


@pytest.mark.acceptance
def test_health_needs_no_authentication(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert not client.cookies
        response = client.get("/health", follow_redirects=False)
    assert response.status_code == 200
    assert "location" not in response.headers


@pytest.mark.acceptance
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_builtin_documentation_is_disabled(settings: Settings, path: str) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get(path, follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.acceptance
@pytest.mark.parametrize("path", ["/static/app.css", "/static/vendor/htmx.min.js"])
def test_static_files_are_served(settings: Settings, path: str) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert len(response.content) > 0


@pytest.mark.acceptance
def test_unknown_static_file_is_not_found(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/static/missing-file.css")
    assert response.status_code == 404


@pytest.mark.acceptance
def test_startup_creates_database_with_app_meta(settings: Settings, database_path: Path) -> None:
    assert not database_path.exists()
    with TestClient(create_app(settings)):
        assert database_path.exists()
        with sqlite3.connect(database_path) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        connection.close()
    assert "app_meta" in tables


@pytest.mark.acceptance
def test_app_state_holds_settings_and_database_path(
    settings: Settings, database_path: Path
) -> None:
    application = create_app(settings)
    with TestClient(application):
        assert application.state.settings is settings
        assert Path(application.state.database_path) == database_path


@pytest.mark.acceptance
def test_second_start_on_same_database_keeps_data(settings: Settings, database_path: Path) -> None:
    with TestClient(create_app(settings)):
        pass
    connection = sqlite3.connect(database_path)
    connection.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", ("probe", "kept"))
    connection.commit()
    connection.close()
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT value FROM app_meta WHERE key = ?", ("probe",)).fetchall()
    finally:
        connection.close()
    assert rows == [("kept",)]


@pytest.mark.acceptance
def test_two_apps_run_simultaneously_on_same_database(
    settings: Settings, database_path: Path
) -> None:
    with TestClient(create_app(settings)) as first, TestClient(create_app(settings)) as second:
        assert first.get("/health").status_code == 200
        assert second.get("/health").status_code == 200
    assert database_path.exists()


@pytest.mark.acceptance
def test_create_app_without_settings_reads_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environ = build_environ(tmp_path / "env-data" / "x.db")
    monkeypatch.chdir(tmp_path)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    with TestClient(create_app(None)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert (tmp_path / "env-data" / "x.db").exists()


@pytest.mark.acceptance
def test_create_app_without_settings_uses_default_argument_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environ = build_environ(tmp_path / "default-arg" / "y.db")
    monkeypatch.chdir(tmp_path)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.acceptance
def test_create_app_without_settings_and_secret_key_fails_naming_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dashboard.settings import ConfigurationError

    environ = build_environ(tmp_path / "missing" / "z.db")
    monkeypatch.chdir(tmp_path)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("SECRET_KEY")
    with pytest.raises(ConfigurationError) as raised:
        create_app(None)
    assert raised.value.variable == "SECRET_KEY"
    assert "SECRET_KEY" in str(raised.value)
    for password in USER_PASSWORDS:
        assert password not in str(raised.value)


@pytest.mark.acceptance
def test_startup_logs_info_record_without_secrets(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="dashboard")
    with TestClient(create_app(settings)) as client:
        client.get("/health")
    records = [
        record
        for record in caplog.records
        if record.name == "dashboard" and record.levelno == logging.INFO
    ]
    assert records
    texts = [record.getMessage() for record in caplog.records] + [caplog.text]
    for text in texts:
        assert SECRET_KEY not in text
        for password in USER_PASSWORDS:
            assert password not in text


@pytest.mark.acceptance
def test_logging_handler_is_added_once(settings: Settings) -> None:
    create_app(settings)
    create_app(settings)
    handlers = [
        handler
        for handler in logging.getLogger("dashboard").handlers
        if handler.get_name() == "dashboard-stdout"
    ]
    assert len(handlers) == 1
    assert logging.getLogger("dashboard").level == logging.INFO


@pytest.mark.acceptance
def test_configure_logging_is_idempotent() -> None:
    main_module.configure_logging()
    main_module.configure_logging()
    main_module.configure_logging()
    names = [handler.get_name() for handler in logging.getLogger("dashboard").handlers]
    assert names.count("dashboard-stdout") == 1


@pytest.mark.acceptance
def test_templates_object_renders_base_html() -> None:
    assert isinstance(templates, Jinja2Templates)
    rendered = templates.get_template("base.html").render()
    assert 'lang="ru"' in rendered
    assert "/static/app.css" in rendered
    assert "/static/vendor/htmx.min.js" in rendered
    assert 'name="viewport"' in rendered


@pytest.mark.acceptance
def test_templates_escape_html_in_child_block() -> None:
    child = templates.env.from_string(
        '{% extends "base.html" %}{% block content %}{{ value }}{% endblock %}'
    )
    rendered = child.render(value="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


@pytest.mark.acceptance
def test_navigation_hidden_without_current_user() -> None:
    rendered = templates.get_template("base.html").render()
    assert "<nav" not in rendered
