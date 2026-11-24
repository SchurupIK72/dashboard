import base64
import re
import time

import pytest

from dashboard.passwords import DUMMY_PASSWORD_HASH, hash_password, verify_password

PASSWORD = "correct horse battery staple"
STORED_FORMAT = re.compile(r"^scrypt\$16384\$8\$1\$[A-Za-z0-9+/]+=*\$[A-Za-z0-9+/]+=*$")


@pytest.fixture(scope="module")
def stored_hash() -> str:
    return hash_password(PASSWORD)


def replace_part(stored: str, index: int, value: str) -> str:
    parts = stored.split("$")
    parts[index] = value
    return "$".join(parts)


@pytest.mark.acceptance
def test_hash_has_documented_format(stored_hash: str) -> None:
    assert STORED_FORMAT.match(stored_hash)
    assert stored_hash.isascii()
    parts = stored_hash.split("$")
    assert len(parts) == 6
    assert len(base64.b64decode(parts[4], validate=True)) == 16
    assert len(base64.b64decode(parts[5], validate=True)) == 32


@pytest.mark.acceptance
def test_verify_accepts_correct_password(stored_hash: str) -> None:
    assert verify_password(PASSWORD, stored_hash) is True


@pytest.mark.acceptance
def test_verify_rejects_wrong_password(stored_hash: str) -> None:
    assert verify_password(PASSWORD + "x", stored_hash) is False
    assert verify_password("", stored_hash) is False
    assert verify_password(PASSWORD.upper(), stored_hash) is False


@pytest.mark.acceptance
def test_two_hashes_of_same_password_differ_and_both_verify(stored_hash: str) -> None:
    other = hash_password(PASSWORD)
    assert other != stored_hash
    assert other.split("$")[4] != stored_hash.split("$")[4]
    assert verify_password(PASSWORD, other) is True


@pytest.mark.acceptance
def test_non_ascii_password_roundtrip() -> None:
    password = "пароль-Вьетнам-密码"
    stored = hash_password(password)
    assert verify_password(password, stored) is True
    assert verify_password("пароль-Вьетнам", stored) is False


@pytest.mark.acceptance
def test_empty_password_can_be_hashed_and_verified() -> None:
    stored = hash_password("")
    assert verify_password("", stored) is True
    assert verify_password(" ", stored) is False


@pytest.mark.acceptance
@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "scrypt",
        "$",
        "$$$$$",
        "plaintext-password",
        "scrypt$16384$8$1$c2FsdA==",
        "scrypt$16384$8$1$c2FsdA==$aGFzaA==$extra",
        "bcrypt$16384$8$1$c2FsdA==$aGFzaA==",
        "SCRYPT$16384$8$1$c2FsdA==$aGFzaA==",
        "scrypt$abc$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$x$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$y$c2FsdA==$aGFzaA==",
        "scrypt$$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$$c2FsdA==$aGFzaA==",
        "scrypt$0$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$0$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$0$c2FsdA==$aGFzaA==",
        "scrypt$-16384$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$-8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$-1$c2FsdA==$aGFzaA==",
        "scrypt$16384.0$8$1$c2FsdA==$aGFzaA==",
        "scrypt$1e4$8$1$c2FsdA==$aGFzaA==",
        "scrypt$ 16384$8$1$c2FsdA==$aGFzaA==",
        "scrypt$٣$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$1$!!!notbase64$aGFzaA==",
        "scrypt$16384$8$1$c2FsdA==$!!!notbase64",
        "scrypt$16384$8$1$c2FsdA=$aGFzaA==",
        "scrypt$16384$8$1$$aGFzaA==",
        "scrypt$16384$8$1$c2FsdA==$",
        "scrypt$16384$8$1$$",
        "scrypt$16384$8$1$пароль$aGFzaA==",
        "scrypt$16384$8$1$c2FsdA==$пароль",
        "пароль$16384$8$1$c2FsdA==$aGFzaA==",
        "scrypt$99999999999999999999999999$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$99999999999999999999999999$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$99999999999999999999999999$c2FsdA==$aGFzaA==",
    ],
)
def test_verify_returns_false_for_malformed_stored_hash(malformed: str) -> None:
    assert verify_password(PASSWORD, malformed) is False


@pytest.mark.acceptance
def test_verify_returns_false_for_tampered_parts(stored_hash: str) -> None:
    parts = stored_hash.split("$")
    flipped = base64.b64encode(bytes(b ^ 1 for b in base64.b64decode(parts[5]))).decode("ascii")
    assert verify_password(PASSWORD, replace_part(stored_hash, 5, flipped)) is False
    other_salt = base64.b64encode(b"\x00" * 16).decode("ascii")
    assert verify_password(PASSWORD, replace_part(stored_hash, 4, other_salt)) is False
    assert verify_password(PASSWORD, replace_part(stored_hash, 1, "32768")) is False


@pytest.mark.acceptance
@pytest.mark.parametrize(
    ("index", "value"),
    [
        (1, str(2**20 + 1)),
        (1, str(2**40)),
        (1, str(2**20)),
        (2, "33"),
        (2, "1000000"),
        (3, "33"),
        (3, "1000000"),
    ],
)
def test_verify_rejects_absurd_parameters_quickly(stored_hash: str, index: int, value: str) -> None:
    started = time.perf_counter()
    result = verify_password(PASSWORD, replace_part(stored_hash, index, value))
    elapsed = time.perf_counter() - started
    assert result is False
    assert elapsed < 2.0


@pytest.mark.acceptance
def test_dummy_hash_has_valid_format_and_rejects_any_password() -> None:
    assert STORED_FORMAT.match(DUMMY_PASSWORD_HASH)
    for attempt in ("", PASSWORD, "admin", "dummy", DUMMY_PASSWORD_HASH):
        assert verify_password(attempt, DUMMY_PASSWORD_HASH) is False


@pytest.mark.acceptance
def test_dummy_hash_is_not_derived_from_a_known_password() -> None:
    assert DUMMY_PASSWORD_HASH != hash_password("")
    assert DUMMY_PASSWORD_HASH.split("$")[4] != hash_password("").split("$")[4]
