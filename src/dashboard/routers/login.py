import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response

from dashboard.database import get_connection
from dashboard.login_attempts import LoginAttempts
from dashboard.session_cookie import SessionSigner, clear_session_cookie, set_session_cookie
from dashboard.users import authenticate

BLOCKED_MESSAGE = "Слишком много попыток входа. Повторите позже."
INVALID_CREDENTIALS_MESSAGE = "Неверный логин или пароль"
LOGIN_TEMPLATE = "login.html"
LOGIN_PATH = "/login"
HOME_PATH = "/"

router = APIRouter()


def _render_login(request: Request, status_code: int, error: str | None) -> Response:
    from dashboard.main import templates

    return templates.TemplateResponse(
        request, LOGIN_TEMPLATE, {"error": error}, status_code=status_code
    )


@router.get(LOGIN_PATH)
def show_login(request: Request) -> Response:
    """Render the login form."""
    return _render_login(request, 200, None)


@router.post(LOGIN_PATH)
def submit_login(
    request: Request,
    login: Annotated[str, Form()],
    password: Annotated[str, Form()],
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> Response:
    """Check the credentials and start a session or answer with the matching error page."""
    login_attempts: LoginAttempts = request.app.state.login_attempts
    if login_attempts.is_blocked(login):
        return _render_login(request, 429, BLOCKED_MESSAGE)
    user = authenticate(connection, login, password)
    if user is None:
        login_attempts.register_failure(login)
        return _render_login(request, 401, INVALID_CREDENTIALS_MESSAGE)
    login_attempts.register_success(login)
    session_signer: SessionSigner = request.app.state.session_signer
    response = RedirectResponse(HOME_PATH, status_code=303)
    set_session_cookie(
        response, session_signer.sign(user.id), request.app.state.settings.cookie_secure
    )
    return response


@router.post("/logout")
def submit_logout() -> Response:
    """End the session and send the user back to the login page."""
    response = RedirectResponse(LOGIN_PATH, status_code=303)
    clear_session_cookie(response)
    return response
