import sqlite3
from typing import Annotated

from fastapi import Depends, Request

from dashboard.database import get_connection
from dashboard.session_cookie import SESSION_COOKIE_NAME
from dashboard.users import User, get_user

OPEN_PATHS = frozenset({"/login", "/health"})


class LoginRequiredError(Exception):
    """Raised when a request has no valid session."""


def require_user(
    request: Request, connection: Annotated[sqlite3.Connection, Depends(get_connection)]
) -> None:
    """Resolve the session user into request.state.user or demand a login."""
    if request.url.path in OPEN_PATHS:
        return
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise LoginRequiredError
    user_id = request.app.state.session_signer.read(token)
    if user_id is None:
        raise LoginRequiredError
    user = get_user(connection, user_id)
    if user is None:
        raise LoginRequiredError
    request.state.user = user


def current_user(request: Request) -> User:
    """Return the user resolved by require_user for this request."""
    user: User = request.state.user
    return user
