import time
from collections.abc import Callable
from dataclasses import dataclass, field

MAX_FAILURES = 5
WINDOW_SECONDS = 300
BLOCK_SECONDS = 300
MAX_TRACKED_LOGINS = 1000


@dataclass
class LoginFailures:
    """Failure timestamps, block deadline and last activity of one login string."""

    last_activity: float
    timestamps: list[float] = field(default_factory=list)
    blocked_until: float | None = None

    def is_blocked_at(self, now: float) -> bool:
        """Report whether the login string is under an active block at the given time."""
        return self.blocked_until is not None and now < self.blocked_until


class LoginAttempts:
    """In-memory counter of failed logins per entered login string."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures_by_login: dict[str, LoginFailures] = {}

    def is_blocked(self, login: str) -> bool:
        """Return True while the login string is blocked."""
        now = self._clock()
        failures = self._current_failures(login, now)
        return failures is not None and failures.is_blocked_at(now)

    def register_failure(self, login: str) -> None:
        """Record a failed attempt and start a block on the fifth failure in the window."""
        now = self._clock()
        failures = self._current_failures(login, now)
        if failures is None:
            self._make_room(now)
            failures = LoginFailures(last_activity=now)
            self._failures_by_login[login] = failures
        elif failures.is_blocked_at(now):
            return
        failures.timestamps.append(now)
        failures.last_activity = now
        if len(failures.timestamps) >= MAX_FAILURES:
            failures.timestamps.clear()
            failures.blocked_until = now + BLOCK_SECONDS

    def register_success(self, login: str) -> None:
        """Forget all failures and any block of the login string."""
        self._failures_by_login.pop(login, None)

    def _current_failures(self, login: str, now: float) -> LoginFailures | None:
        failures = self._failures_by_login.get(login)
        if failures is None:
            return None
        if failures.is_blocked_at(now):
            return failures
        failures.blocked_until = None
        failures.timestamps = [
            timestamp for timestamp in failures.timestamps if now - timestamp <= WINDOW_SECONDS
        ]
        if not failures.timestamps:
            del self._failures_by_login[login]
            return None
        return failures

    def _make_room(self, now: float) -> None:
        if len(self._failures_by_login) < MAX_TRACKED_LOGINS:
            return
        entries = list(self._failures_by_login.items())
        unblocked = [entry for entry in entries if not entry[1].is_blocked_at(now)]
        oldest_login, _ = min(unblocked or entries, key=lambda entry: entry[1].last_activity)
        del self._failures_by_login[oldest_login]
