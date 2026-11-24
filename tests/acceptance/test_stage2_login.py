import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from dashboard.current_user import current_user
from dashboard.main import create_app
from dashboard.settings import Settings, load_settings
from dashboard.users import User

SECRET_KEY = "k9Zq-login-secret-0123456789-abcdefXYZ"
PASSWORDS = {"anna": "pw-anna-7731", "boris": "pw-boris-4482", "vera": "pw-vera-9915"}
USERS = [
    {"login": "anna", "password": PASSWORDS["anna"], "company": "Alpha"},
    {"login": "boris", "password": PASSWORDS["boris"], "company": "Alpha"},
    {"login": "vera", "password": PASSWORDS["vera"], "company": "Beta"},
]
CANARY_PASSWORD = "wrong-canary-5503-zq"
INVALID_MESSAGE = "Неверный логин или пароль"
BLOCKED_MESSAGE = "Слишком много попыток входа"
COOKIE_NAME = "dashboard_session"
MONTH_SECONDS = 30 * 24 * 60 * 60


def build_settings(database_path: Path, cookie_secure: str | None = None) -> Settings:
    environ = {
        "SECRET_KEY": SECRET_KEY,
        "DASHBOARD_USERS": json.dumps(USERS),
        "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
    }
    if cookie_secure is not None:
        environ["COOKIE_SECURE"] = cookie_secure
    return load_settings(environ=environ, env_file=None)


def add_probe(application: FastAPI) -> None:
    @application.get("/__probe")
    def read_probe(user: Annotated[User, Depends(current_user)]) -> dict[str, str]:
        return {"login": user.login}


def build_client(database_path: Path, cookie_secure: str | None = None) -> TestClient:
    application = create_app(build_settings(database_path, cookie_secure))
    add_probe(application)
    return TestClient(application, follow_redirects=False)


def cookie_attributes(set_cookie: str) -> list[str]:
    return [part.strip().lower() for part in set_cookie.split(";")]


def session_set_cookies(response_headers: list[str]) -> list[str]:
    return [header for header in response_headers if header.startswith(f"{COOKIE_NAME}=")]


def post_login(client: TestClient, login: str, password: str) -> Response:
    return client.post("/login", data={"login": login, "password": password})


@pytest.fixture(scope="module")
def shared_client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    database_path = tmp_path_factory.mktemp("login") / "dashboard.db"
    with build_client(database_path) as client:
        yield client


@pytest.fixture
def client(shared_client: TestClient) -> Iterator[TestClient]:
    shared_client.cookies.clear()
    yield shared_client
    shared_client.cookies.clear()


@pytest.mark.acceptance
def test_login_page_shows_password_form_without_navigation(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert re.search(r'<input[^>]*type="password"', response.text)
    assert 'name="login"' in response.text
    assert 'name="password"' in response.text
    assert "<nav" not in response.text
    assert "Вход" in response.text


@pytest.mark.acceptance
def test_login_success_redirects_home_with_session_cookie(client: TestClient) -> None:
    response = post_login(client, "anna", PASSWORDS["anna"])
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookies = session_set_cookies(response.headers.get_list("set-cookie"))
    assert len(cookies) == 1
    attributes = cookie_attributes(cookies[0])
    assert "httponly" in attributes
    assert "samesite=lax" in attributes
    assert f"max-age={MONTH_SECONDS}" in attributes
    assert "path=/" in attributes
    assert "secure" not in attributes
    assert client.get("/__probe").json() == {"login": "anna"}


@pytest.mark.acceptance
def test_login_cookie_is_secure_when_configured(tmp_path: Path) -> None:
    with build_client(tmp_path / "secure.db", cookie_secure="true") as secure_client:
        response = post_login(secure_client, "vera", PASSWORDS["vera"])
    assert response.status_code == 303
    cookies = session_set_cookies(response.headers.get_list("set-cookie"))
    assert len(cookies) == 1
    attributes = cookie_attributes(cookies[0])
    assert "secure" in attributes
    assert "httponly" in attributes
    assert "samesite=lax" in attributes


@pytest.mark.acceptance
def test_each_user_logs_in_as_themselves(client: TestClient) -> None:
    for login in ("boris", "vera"):
        client.cookies.clear()
        response = post_login(client, login, PASSWORDS[login])
        assert response.status_code == 303
        assert client.get("/__probe").json() == {"login": login}


@pytest.mark.acceptance
def test_unknown_login_and_wrong_password_give_identical_response(client: TestClient) -> None:
    unknown = post_login(client, "nobody-here", "whatever-123")
    wrong = post_login(client, "anna", "definitely-not-it")
    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.text == wrong.text
    assert INVALID_MESSAGE in unknown.text
    assert "set-cookie" not in unknown.headers
    assert "set-cookie" not in wrong.headers
    assert 'class="error"' in unknown.text
    assert "<nav" not in unknown.text


@pytest.mark.acceptance
def test_failed_login_does_not_grant_access(client: TestClient) -> None:
    post_login(client, "anna", "definitely-not-it")
    response = client.get("/__probe")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_html_in_login_field_is_not_reflected_unescaped(client: TestClient) -> None:
    payload = '<script>alert("x")</script>'
    response = post_login(client, payload, "whatever-123")
    assert response.status_code == 401
    assert payload not in response.text
    assert "<script>alert" not in response.text


@pytest.mark.acceptance
def test_sixth_attempt_after_five_failures_is_blocked_even_with_right_password(
    client: TestClient,
) -> None:
    for _ in range(5):
        assert post_login(client, "boris", "wrong-pass").status_code == 401
    response = post_login(client, "boris", PASSWORDS["boris"])
    assert response.status_code == 429
    assert BLOCKED_MESSAGE in response.text
    assert "set-cookie" not in response.headers
    assert client.get("/__probe").status_code == 303


@pytest.mark.acceptance
def test_blocked_login_stays_blocked_on_further_attempts(client: TestClient) -> None:
    for _ in range(5):
        post_login(client, "ghost-repeat", "wrong-pass")
    for _ in range(3):
        response = post_login(client, "ghost-repeat", "another-pass")
        assert response.status_code == 429
        assert BLOCKED_MESSAGE in response.text


@pytest.mark.acceptance
def test_five_failures_for_nonexistent_login_block_that_string(client: TestClient) -> None:
    for _ in range(5):
        assert post_login(client, "ghost-login", "wrong-pass").status_code == 401
    response = post_login(client, "ghost-login", "wrong-pass")
    assert response.status_code == 429
    assert BLOCKED_MESSAGE in response.text
    assert "set-cookie" not in response.headers


@pytest.mark.acceptance
def test_blocked_login_does_not_block_another_login(client: TestClient) -> None:
    for _ in range(5):
        post_login(client, "ghost-other", "wrong-pass")
    assert post_login(client, "ghost-other", "wrong-pass").status_code == 429
    response = post_login(client, "anna", PASSWORDS["anna"])
    assert response.status_code == 303
    other_failure = post_login(client, "ghost-neighbour", "wrong-pass")
    assert other_failure.status_code == 401


@pytest.mark.acceptance
def test_four_failures_do_not_block(client: TestClient) -> None:
    for _ in range(4):
        assert post_login(client, "ghost-four", "wrong-pass").status_code == 401
    unknown_again = post_login(client, "ghost-four", "wrong-pass")
    assert unknown_again.status_code == 401


@pytest.mark.acceptance
def test_success_resets_failure_counter(client: TestClient) -> None:
    for _ in range(4):
        assert post_login(client, "vera", "wrong-pass").status_code == 401
    assert post_login(client, "vera", PASSWORDS["vera"]).status_code == 303
    for _ in range(4):
        assert post_login(client, "vera", "wrong-pass").status_code == 401
    assert post_login(client, "vera", PASSWORDS["vera"]).status_code == 303


@pytest.mark.acceptance
def test_logout_expires_cookie_and_redirects_to_login(client: TestClient) -> None:
    assert post_login(client, "anna", PASSWORDS["anna"]).status_code == 303
    assert client.get("/__probe").status_code == 200
    response = client.post("/logout")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    cookies = session_set_cookies(response.headers.get_list("set-cookie"))
    assert len(cookies) == 1
    attributes = cookie_attributes(cookies[0])
    assert "max-age=0" in attributes
    assert "path=/" in attributes


@pytest.mark.acceptance
def test_after_logout_protected_routes_redirect_again(client: TestClient) -> None:
    assert post_login(client, "anna", PASSWORDS["anna"]).status_code == 303
    client.post("/logout")
    response = client.get("/__probe")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert not client.cookies.get(COOKIE_NAME)


@pytest.mark.acceptance
def test_logout_without_session_redirects_to_login(client: TestClient) -> None:
    response = client.post("/logout")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.acceptance
def test_logout_is_post_only(client: TestClient) -> None:
    assert post_login(client, "anna", PASSWORDS["anna"]).status_code == 303
    response = client.get("/logout")
    assert response.status_code in (303, 405)
    assert client.get("/__probe").status_code == 200


@pytest.mark.acceptance
def test_password_never_appears_in_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    post_login(client, "anna", CANARY_PASSWORD)
    post_login(client, "ghost-logging", CANARY_PASSWORD)
    post_login(client, "anna", PASSWORDS["anna"])
    client.post("/logout")
    texts = [record.getMessage() for record in caplog.records] + [caplog.text]
    for text in texts:
        assert CANARY_PASSWORD not in text
        assert PASSWORDS["anna"] not in text
