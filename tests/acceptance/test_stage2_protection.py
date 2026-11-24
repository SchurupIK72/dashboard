import json
import logging
import sqlite3
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner, URLSafeTimedSerializer

from dashboard.current_user import current_user
from dashboard.main import create_app
from dashboard.session_cookie import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, SESSION_SALT
from dashboard.settings import Settings, load_settings
from dashboard.users import User, UserSeedError

SECRET_KEY = "k9Zq-guard-secret-0123456789-abcdefXYZ"
OTHER_SECRET_KEY = "another-secret-key-0123456789-abcdefXYZ"
PASSWORDS = {"anna": "pw-anna-7731", "boris": "pw-boris-4482", "vera": "pw-vera-9915"}
USERS = [
    {"login": "anna", "password": PASSWORDS["anna"], "company": "Alpha"},
    {"login": "boris", "password": PASSWORDS["boris"], "company": "Alpha"},
    {"login": "vera", "password": PASSWORDS["vera"], "company": "Beta"},
]
OPEN_PATHS = {"/login", "/health"}


def build_settings(database_path: Path, users: list[dict[str, str]] | None = None) -> Settings:
    environ = {
        "SECRET_KEY": SECRET_KEY,
        "DASHBOARD_USERS": json.dumps(USERS if users is None else users),
        "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
    }
    return load_settings(environ=environ, env_file=None)


def add_probe(application: FastAPI) -> None:
    @application.get("/__probe")
    def read_probe(user: Annotated[User, Depends(current_user)]) -> dict[str, str]:
        return {"login": user.login}


def build_application(database_path: Path, users: list[dict[str, str]] | None = None) -> FastAPI:
    application = create_app(build_settings(database_path, users))
    add_probe(application)
    return application


def cookie_header(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


class BackdatedSigner(TimestampSigner):
    age_seconds = 0

    def get_timestamp(self) -> int:
        return int(time.time()) - type(self).age_seconds


def craft_token(secret_key: str, payload: object, age_seconds: int = 0) -> str:
    signer_class = type("AgedSigner", (BackdatedSigner,), {"age_seconds": age_seconds})
    serializer = URLSafeTimedSerializer(secret_key, salt=SESSION_SALT, signer=signer_class)
    token: str = serializer.dumps(payload)
    return token


def collect_api_routes(routes: Sequence[object]) -> list[APIRoute]:
    collected: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            collected.append(route)
            continue
        included = getattr(route, "original_router", None)
        if included is not None:
            collected.extend(collect_api_routes(included.routes))
    return collected


def read_rows(database_path: Path, sql: str) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(database_path)
    try:
        return [tuple(row) for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()


@pytest.fixture(scope="module")
def guarded_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("guard") / "dashboard.db"


@pytest.fixture(scope="module")
def application(guarded_database: Path) -> FastAPI:
    return build_application(guarded_database)


@pytest.fixture(scope="module")
def client(application: FastAPI) -> Iterator[TestClient]:
    with TestClient(application, follow_redirects=False) as running_client:
        yield running_client


@pytest.fixture(scope="module")
def session_token(client: TestClient) -> str:
    response = client.post("/login", data={"login": "boris", "password": PASSWORDS["boris"]})
    assert response.status_code == 303
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token
    client.cookies.clear()
    return token


@pytest.mark.acceptance
def test_request_without_cookie_redirects_to_login(client: TestClient) -> None:
    response = client.get("/__probe")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_htmx_request_without_cookie_gets_hx_redirect(client: TestClient) -> None:
    response = client.get("/__probe", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["HX-Redirect"] == "/login"
    assert "location" not in response.headers


@pytest.mark.acceptance
def test_htmx_request_with_invalid_cookie_gets_hx_redirect(client: TestClient) -> None:
    headers = {"HX-Request": "true", **cookie_header("garbage")}
    response = client.get("/__probe", headers=headers)
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["HX-Redirect"] == "/login"


@pytest.mark.acceptance
def test_non_htmx_header_value_still_redirects_with_303(client: TestClient) -> None:
    response = client.get("/__probe", headers={"HX-Request": "false"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "HX-Redirect" not in response.headers


@pytest.mark.acceptance
def test_real_login_cookie_gives_access_with_current_user(
    client: TestClient, session_token: str
) -> None:
    response = client.get("/__probe", headers=cookie_header(session_token))
    assert response.status_code == 200
    assert response.json() == {"login": "boris"}


@pytest.mark.acceptance
def test_token_signed_by_server_for_other_user_id_identifies_that_user(
    client: TestClient, application: FastAPI
) -> None:
    token = application.state.session_signer.sign(3)
    response = client.get("/__probe", headers=cookie_header(token))
    assert response.status_code == 200
    assert response.json() == {"login": "vera"}


@pytest.mark.acceptance
def test_tampered_signature_is_rejected(client: TestClient, session_token: str) -> None:
    payload, timestamp, signature = session_token.split(".")
    flipped = "A" if signature[0] != "A" else "B"
    forged = ".".join((payload, timestamp, flipped + signature[1:]))
    assert forged != session_token
    response = client.get("/__probe", headers=cookie_header(forged))
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_tampered_payload_with_reused_signature_is_rejected(
    client: TestClient, application: FastAPI, session_token: str
) -> None:
    other_payload = application.state.session_signer.sign(1).split(".")[0]
    _, timestamp, signature = session_token.split(".")
    forged = f"{other_payload}.{timestamp}.{signature}"
    response = client.get("/__probe", headers=cookie_header(forged))
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_cookie_signed_with_other_secret_is_rejected(client: TestClient) -> None:
    fresh = client.get("/__probe", headers=cookie_header(craft_token(SECRET_KEY, 1)))
    assert fresh.status_code == 200
    foreign = client.get("/__probe", headers=cookie_header(craft_token(OTHER_SECRET_KEY, 1)))
    assert foreign.status_code == 303
    assert foreign.headers["location"] == "/login"


@pytest.mark.acceptance
def test_cookie_older_than_thirty_days_is_rejected(client: TestClient) -> None:
    almost = craft_token(SECRET_KEY, 1, age_seconds=SESSION_MAX_AGE_SECONDS - 3600)
    assert client.get("/__probe", headers=cookie_header(almost)).status_code == 200
    expired = craft_token(SECRET_KEY, 1, age_seconds=SESSION_MAX_AGE_SECONDS + 3600)
    response = client.get("/__probe", headers=cookie_header(expired))
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_cookie_of_missing_user_id_is_rejected(client: TestClient) -> None:
    response = client.get("/__probe", headers=cookie_header(craft_token(SECRET_KEY, 9999)))
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
@pytest.mark.parametrize("payload", ["not-a-number", None, 1.5, [1], True])
def test_cookie_with_non_integer_payload_is_rejected(client: TestClient, payload: object) -> None:
    response = client.get("/__probe", headers=cookie_header(craft_token(SECRET_KEY, payload)))
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
@pytest.mark.parametrize("value", ["", "garbage", "a.b.c", "x" * 600])
def test_malformed_cookie_values_are_rejected(client: TestClient, value: str) -> None:
    response = client.get("/__probe", headers=cookie_header(value))
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_every_application_route_requires_session_except_open_ones(
    client: TestClient, application: FastAPI
) -> None:
    checked: list[str] = []
    for route in collect_api_routes(application.routes):
        if route.path in OPEN_PATHS:
            continue
        for method in route.methods:
            response = client.request(method, route.path)
            assert response.status_code == 303, (method, route.path)
            assert response.headers["location"] == "/login"
            checked.append(f"{method} {route.path}")
    assert "GET /__probe" in checked
    assert "POST /logout" in checked
    assert {route.path for route in collect_api_routes(application.routes)} >= OPEN_PATHS


@pytest.mark.acceptance
@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/login", "text/html"),
        ("/health", "application/json"),
        ("/static/app.css", "text/css"),
        ("/static/vendor/htmx.min.js", "javascript"),
    ],
)
def test_open_paths_are_served_without_cookie(
    client: TestClient, path: str, content_type: str
) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert len(response.content) > 0


@pytest.mark.acceptance
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_builtin_documentation_is_not_found(
    client: TestClient, path: str, session_token: str
) -> None:
    assert client.get(path).status_code == 404
    assert client.get(path, headers=cookie_header(session_token)).status_code == 404


@pytest.mark.acceptance
def test_startup_creates_three_users_and_two_companies(
    application: FastAPI, client: TestClient, guarded_database: Path
) -> None:
    users = read_rows(guarded_database, "SELECT login FROM users ORDER BY id")
    companies = read_rows(guarded_database, "SELECT name FROM companies ORDER BY id")
    assert users == [("anna",), ("boris",), ("vera",)]
    assert companies == [("Alpha",), ("Beta",)]
    mapping = read_rows(
        guarded_database,
        "SELECT users.login, companies.name FROM users "
        "JOIN companies ON companies.id = users.company_id ORDER BY users.id",
    )
    assert mapping == [("anna", "Alpha"), ("boris", "Alpha"), ("vera", "Beta")]


@pytest.mark.acceptance
def test_stored_password_hashes_are_not_plain_passwords(
    client: TestClient, guarded_database: Path
) -> None:
    hashes = [row[0] for row in read_rows(guarded_database, "SELECT password_hash FROM users")]
    assert len(hashes) == 3
    for stored, password in zip(hashes, PASSWORDS.values(), strict=True):
        assert isinstance(stored, str)
        assert stored.startswith("scrypt$")
        assert password not in stored


@pytest.mark.acceptance
def test_second_start_on_same_database_keeps_users_and_hashes(tmp_path: Path) -> None:
    database_path = tmp_path / "again.db"
    with TestClient(build_application(database_path)):
        pass
    before = read_rows(database_path, "SELECT id, login, password_hash, company_id FROM users")
    companies_before = read_rows(database_path, "SELECT id, name FROM companies")
    with TestClient(build_application(database_path)):
        pass
    after = read_rows(database_path, "SELECT id, login, password_hash, company_id FROM users")
    companies_after = read_rows(database_path, "SELECT id, name FROM companies")
    assert len(before) == 3
    assert before == after
    assert companies_before == companies_after
    assert len(companies_after) == 2


@pytest.mark.acceptance
def test_second_start_ignores_changed_passwords_in_settings(tmp_path: Path) -> None:
    database_path = tmp_path / "passwords.db"
    with TestClient(build_application(database_path)):
        pass
    changed = [{**user, "password": f"changed-{user['password']}"} for user in USERS]
    with TestClient(build_application(database_path, changed), follow_redirects=False) as running:
        old = running.post("/login", data={"login": "anna", "password": PASSWORDS["anna"]})
        new = running.post("/login", data={"login": "vera", "password": "changed-pw-vera-9915"})
    assert old.status_code == 303
    assert new.status_code == 401


@pytest.mark.acceptance
def test_different_login_set_stops_startup(tmp_path: Path) -> None:
    database_path = tmp_path / "logins.db"
    with TestClient(build_application(database_path)):
        pass
    replaced = [*USERS[:2], {"login": "zoya", "password": "pw-zoya-1234", "company": "Beta"}]
    with (
        pytest.raises(UserSeedError) as raised,
        TestClient(build_application(database_path, replaced)),
    ):
        pass
    assert "pw-zoya-1234" not in str(raised.value)
    assert "zoya" in str(raised.value) or "vera" in str(raised.value)
    assert read_rows(database_path, "SELECT login FROM users ORDER BY id") == [
        ("anna",),
        ("boris",),
        ("vera",),
    ]


@pytest.mark.acceptance
def test_different_company_for_one_login_stops_startup(tmp_path: Path) -> None:
    database_path = tmp_path / "company.db"
    with TestClient(build_application(database_path)):
        pass
    regrouped = [
        {**USERS[0], "company": "Beta"},
        {**USERS[1], "company": "Alpha"},
        {**USERS[2], "company": "Beta"},
    ]
    with (
        pytest.raises(UserSeedError) as raised,
        TestClient(build_application(database_path, regrouped)),
    ):
        pass
    assert "anna" in str(raised.value)
    for password in PASSWORDS.values():
        assert password not in str(raised.value)


@pytest.mark.acceptance
def test_four_users_stop_startup_and_seed_nothing(tmp_path: Path) -> None:
    database_path = tmp_path / "four.db"
    four = [*USERS, {"login": "dina", "password": "pw-dina-5566", "company": "Beta"}]
    with pytest.raises(UserSeedError) as raised, TestClient(build_application(database_path, four)):
        pass
    assert "pw-dina-5566" not in str(raised.value)
    assert read_rows(database_path, "SELECT login FROM users") == []


@pytest.mark.acceptance
def test_three_companies_for_three_users_stop_startup(tmp_path: Path) -> None:
    database_path = tmp_path / "three-companies.db"
    spread = [{**user, "company": f"Company{index}"} for index, user in enumerate(USERS)]
    with pytest.raises(UserSeedError), TestClient(build_application(database_path, spread)):
        pass
    assert read_rows(database_path, "SELECT login FROM users") == []


@pytest.mark.acceptance
def test_startup_log_contains_no_seed_password(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    with TestClient(build_application(tmp_path / "logs.db")):
        pass
    with (
        pytest.raises(UserSeedError),
        TestClient(build_application(tmp_path / "logs.db", USERS[:2])),
    ):
        pass
    texts = [record.getMessage() for record in caplog.records] + [caplog.text]
    assert caplog.records
    for text in texts:
        assert SECRET_KEY not in text
        for password in PASSWORDS.values():
            assert password not in text
