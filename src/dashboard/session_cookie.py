from itsdangerous import BadData, URLSafeTimedSerializer
from starlette.responses import Response

SESSION_COOKIE_NAME = "dashboard_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
SESSION_SALT = "dashboard.session"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAMESITE = "lax"


class SessionSigner:
    """Signs and verifies session tokens that carry a user id."""

    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeTimedSerializer(secret_key, salt=SESSION_SALT)

    def sign(self, user_id: int) -> str:
        """Return a signed timestamped token for the user id."""
        token: str = self._serializer.dumps(user_id)
        return token

    def read(self, token: str, max_age_seconds: int = SESSION_MAX_AGE_SECONDS) -> int | None:
        """Return the user id from a valid unexpired token, otherwise None."""
        try:
            payload: object = self._serializer.loads(token, max_age=max_age_seconds)
        except BadData:
            return None
        if isinstance(payload, bool) or not isinstance(payload, int):
            return None
        return payload


def set_session_cookie(response: Response, token: str, secure: bool) -> None:
    """Attach the session cookie to the response."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        path=SESSION_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie on the client."""
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
    )
