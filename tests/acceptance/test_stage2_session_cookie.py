import pytest
from itsdangerous import URLSafeTimedSerializer
from starlette.responses import Response

from dashboard.session_cookie import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    SessionSigner,
    clear_session_cookie,
    set_session_cookie,
)

SECRET = "s" * 40
OTHER_SECRET = "t" * 40


def cookie_header(response: Response) -> str:
    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 1
    return headers[0]


def attributes_of(header: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for chunk in header.split(";")[1:]:
        name, _, value = chunk.strip().partition("=")
        result[name.lower()] = value
    return result


@pytest.mark.acceptance
def test_constants_match_contract() -> None:
    assert SESSION_COOKIE_NAME == "dashboard_session"
    assert SESSION_MAX_AGE_SECONDS == 2592000


@pytest.mark.acceptance
@pytest.mark.parametrize("user_id", [1, 2, 3, 0, 123456789])
def test_sign_read_roundtrip(user_id: int) -> None:
    signer = SessionSigner(SECRET)
    assert signer.read(signer.sign(user_id)) == user_id


@pytest.mark.acceptance
def test_separate_signer_instances_with_same_key_agree() -> None:
    token = SessionSigner(SECRET).sign(7)
    assert SessionSigner(SECRET).read(token) == 7


@pytest.mark.acceptance
def test_tampered_signature_returns_none() -> None:
    signer = SessionSigner(SECRET)
    token = signer.sign(2)
    last = token[-1]
    replacement = "A" if last != "A" else "B"
    assert signer.read(token[:-1] + replacement) is None


@pytest.mark.acceptance
def test_tampered_payload_returns_none() -> None:
    signer = SessionSigner(SECRET)
    first = signer.sign(2)
    second = signer.sign(3)
    forged = second.split(".")[0] + "." + first.split(".", 1)[1]
    assert signer.read(forged) is None


@pytest.mark.acceptance
def test_token_signed_with_other_secret_returns_none() -> None:
    token = SessionSigner(OTHER_SECRET).sign(1)
    assert SessionSigner(SECRET).read(token) is None


@pytest.mark.acceptance
@pytest.mark.parametrize(
    "garbage",
    ["", "garbage", "a.b.c", ".", "..", "1", "пароль", " ", "\x00", "x" * 5000],
)
def test_garbage_returns_none_without_raising(garbage: str) -> None:
    assert SessionSigner(SECRET).read(garbage) is None


@pytest.mark.acceptance
def test_expired_token_returns_none() -> None:
    signer = SessionSigner(SECRET)
    token = signer.sign(1)
    assert signer.read(token, max_age_seconds=-1) is None


@pytest.mark.acceptance
def test_fresh_token_is_valid_for_default_and_explicit_max_age() -> None:
    signer = SessionSigner(SECRET)
    token = signer.sign(4)
    assert signer.read(token, max_age_seconds=60) == 4
    assert signer.read(token, max_age_seconds=SESSION_MAX_AGE_SECONDS) == 4


@pytest.mark.acceptance
def test_default_max_age_is_thirty_days() -> None:
    signer = SessionSigner(SECRET)
    serializer = URLSafeTimedSerializer(SECRET, salt="dashboard.session")
    assert signer.read(signer.sign(1)) == 1
    assert serializer.loads(signer.sign(1), max_age=SESSION_MAX_AGE_SECONDS) == 1


@pytest.mark.acceptance
@pytest.mark.parametrize("payload", ["5", "abc", None, 1.5, [1], {"id": 1}, True, False])
def test_non_int_payload_with_valid_signature_returns_none(payload: object) -> None:
    signer = SessionSigner(SECRET)
    foreign = URLSafeTimedSerializer(SECRET, salt="dashboard.session")
    token = foreign.dumps(payload)
    assert signer.read(token) is None


@pytest.mark.acceptance
def test_token_signed_with_other_salt_returns_none() -> None:
    token = URLSafeTimedSerializer(SECRET, salt="another.salt").dumps(1)
    assert SessionSigner(SECRET).read(token) is None


@pytest.mark.acceptance
def test_set_session_cookie_secure_false_header() -> None:
    response = Response()
    set_session_cookie(response, "tok", secure=False)
    header = cookie_header(response)
    assert header.startswith("dashboard_session=tok")
    attributes = attributes_of(header)
    assert "httponly" in attributes
    assert attributes["samesite"].lower() == "lax"
    assert attributes["max-age"] == "2592000"
    assert attributes["path"] == "/"
    assert "secure" not in attributes


@pytest.mark.acceptance
def test_set_session_cookie_secure_true_header() -> None:
    response = Response()
    set_session_cookie(response, "tok", secure=True)
    attributes = attributes_of(cookie_header(response))
    assert "secure" in attributes
    assert "httponly" in attributes
    assert attributes["samesite"].lower() == "lax"
    assert attributes["max-age"] == "2592000"
    assert attributes["path"] == "/"


@pytest.mark.acceptance
def test_set_session_cookie_carries_real_signed_token() -> None:
    signer = SessionSigner(SECRET)
    token = signer.sign(3)
    response = Response()
    set_session_cookie(response, token, secure=False)
    header = cookie_header(response)
    value = header.split(";")[0].split("=", 1)[1]
    assert signer.read(value) == 3


@pytest.mark.acceptance
def test_clear_session_cookie_expires_with_matching_path() -> None:
    response = Response()
    clear_session_cookie(response)
    header = cookie_header(response)
    assert header.startswith("dashboard_session=")
    attributes = attributes_of(header)
    assert attributes["max-age"] == "0"
    assert attributes["path"] == "/"
    assert "httponly" in attributes
    assert attributes["samesite"].lower() == "lax"
    assert header.split(";")[0] in ("dashboard_session=", 'dashboard_session=""')


@pytest.mark.acceptance
def test_set_and_clear_use_same_cookie_name_and_path() -> None:
    set_response = Response()
    set_session_cookie(set_response, "tok", secure=False)
    clear_response = Response()
    clear_session_cookie(clear_response)
    set_attributes = attributes_of(cookie_header(set_response))
    clear_attributes = attributes_of(cookie_header(clear_response))
    assert cookie_header(set_response).split("=")[0] == cookie_header(clear_response).split("=")[0]
    assert set_attributes["path"] == clear_attributes["path"]
