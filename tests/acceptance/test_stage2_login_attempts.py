import pytest

from dashboard.login_attempts import (
    BLOCK_SECONDS,
    MAX_FAILURES,
    MAX_TRACKED_LOGINS,
    WINDOW_SECONDS,
    LoginAttempts,
)


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def fail_times(attempts: LoginAttempts, login: str, count: int) -> None:
    for _ in range(count):
        attempts.register_failure(login)


@pytest.mark.acceptance
def test_constants_match_contract() -> None:
    assert MAX_FAILURES == 5
    assert WINDOW_SECONDS == 300
    assert BLOCK_SECONDS == 300
    assert MAX_TRACKED_LOGINS == 1000


@pytest.mark.acceptance
def test_unknown_login_is_not_blocked() -> None:
    attempts = LoginAttempts(FakeClock())
    assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_four_failures_do_not_block() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    for _ in range(4):
        attempts.register_failure("anna")
        clock.advance(1)
        assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_fifth_failure_blocks() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 4)
    assert attempts.is_blocked("anna") is False
    attempts.register_failure("anna")
    assert attempts.is_blocked("anna") is True


@pytest.mark.acceptance
def test_block_holds_until_300_seconds_after_block_start() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 5)
    clock.advance(299)
    assert attempts.is_blocked("anna") is True
    clock.advance(1)
    assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_block_is_measured_from_the_fifth_failure() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 4)
    clock.advance(100)
    attempts.register_failure("anna")
    clock.advance(299)
    assert attempts.is_blocked("anna") is True
    clock.advance(1)
    assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_after_block_ends_login_starts_with_clean_counter() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 5)
    clock.advance(301)
    assert attempts.is_blocked("anna") is False
    fail_times(attempts, "anna", 4)
    assert attempts.is_blocked("anna") is False
    attempts.register_failure("anna")
    assert attempts.is_blocked("anna") is True


@pytest.mark.acceptance
def test_failures_spread_beyond_window_never_block() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    for _ in range(20):
        attempts.register_failure("anna")
        assert attempts.is_blocked("anna") is False
        clock.advance(100)
    assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_old_failures_are_dropped_from_window() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 4)
    clock.advance(400)
    fail_times(attempts, "anna", 4)
    assert attempts.is_blocked("anna") is False
    attempts.register_failure("anna")
    assert attempts.is_blocked("anna") is True


@pytest.mark.acceptance
def test_success_resets_counter() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 4)
    attempts.register_success("anna")
    fail_times(attempts, "anna", 4)
    assert attempts.is_blocked("anna") is False
    attempts.register_failure("anna")
    assert attempts.is_blocked("anna") is True


@pytest.mark.acceptance
def test_success_of_unknown_login_does_not_raise() -> None:
    attempts = LoginAttempts(FakeClock())
    attempts.register_success("nobody")
    assert attempts.is_blocked("nobody") is False


@pytest.mark.acceptance
def test_success_clears_active_block() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 5)
    attempts.register_success("anna")
    assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_logins_are_independent() -> None:
    attempts = LoginAttempts(FakeClock())
    fail_times(attempts, "anna", 5)
    assert attempts.is_blocked("anna") is True
    assert attempts.is_blocked("boris") is False
    fail_times(attempts, "boris", 4)
    assert attempts.is_blocked("boris") is False


@pytest.mark.acceptance
def test_unknown_login_strings_are_counted_and_blocked() -> None:
    attempts = LoginAttempts(FakeClock())
    fail_times(attempts, "no-such-user", 5)
    assert attempts.is_blocked("no-such-user") is True
    assert attempts.is_blocked("no-such-user2") is False


@pytest.mark.acceptance
def test_login_strings_are_matched_as_typed() -> None:
    attempts = LoginAttempts(FakeClock())
    fail_times(attempts, "Anna", 5)
    assert attempts.is_blocked("Anna") is True
    assert attempts.is_blocked("anna") is False
    assert attempts.is_blocked("Anna ") is False


@pytest.mark.acceptance
def test_failure_during_block_does_not_extend_block() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 5)
    clock.advance(200)
    fail_times(attempts, "anna", 10)
    assert attempts.is_blocked("anna") is True
    clock.advance(99)
    assert attempts.is_blocked("anna") is True
    clock.advance(1)
    assert attempts.is_blocked("anna") is False


@pytest.mark.acceptance
def test_failure_during_block_adds_no_failures() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "anna", 5)
    fail_times(attempts, "anna", 20)
    clock.advance(300)
    assert attempts.is_blocked("anna") is False
    fail_times(attempts, "anna", 4)
    assert attempts.is_blocked("anna") is False
    attempts.register_failure("anna")
    assert attempts.is_blocked("anna") is True


@pytest.mark.acceptance
def test_tracked_logins_are_capped_at_1000() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    for index in range(1005):
        attempts.register_failure(f"user-{index}")
        clock.advance(1)
    tracked = attempts._failures_by_login
    assert len(tracked) <= MAX_TRACKED_LOGINS
    assert len(tracked) == MAX_TRACKED_LOGINS


@pytest.mark.acceptance
def test_oldest_unblocked_login_is_evicted_first() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    for index in range(1005):
        attempts.register_failure(f"user-{index}")
        clock.advance(1)
    tracked = attempts._failures_by_login
    assert "user-0" not in tracked
    assert "user-1004" in tracked


@pytest.mark.acceptance
def test_actively_blocked_login_survives_eviction() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "victim", 5)
    clock.advance(1)
    for index in range(1005):
        attempts.register_failure(f"user-{index}")
        clock.advance(0.01)
    assert attempts.is_blocked("victim") is True
    assert len(attempts._failures_by_login) <= MAX_TRACKED_LOGINS


@pytest.mark.acceptance
def test_eviction_forgets_evicted_login_failures() -> None:
    clock = FakeClock()
    attempts = LoginAttempts(clock)
    fail_times(attempts, "first", 4)
    clock.advance(1)
    for index in range(1000):
        attempts.register_failure(f"user-{index}")
        clock.advance(1)
    assert attempts.is_blocked("first") is False
    attempts.register_failure("first")
    assert attempts.is_blocked("first") is False


@pytest.mark.acceptance
def test_instances_are_independent() -> None:
    first = LoginAttempts(FakeClock())
    second = LoginAttempts(FakeClock())
    fail_times(first, "anna", 5)
    assert first.is_blocked("anna") is True
    assert second.is_blocked("anna") is False
    fail_times(second, "anna", 4)
    assert second.is_blocked("anna") is False


@pytest.mark.acceptance
def test_default_clock_is_usable() -> None:
    attempts = LoginAttempts()
    fail_times(attempts, "anna", 5)
    assert attempts.is_blocked("anna") is True
    attempts.register_success("anna")
    assert attempts.is_blocked("anna") is False
