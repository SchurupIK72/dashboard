import json
from pathlib import Path

import pytest

from dashboard.settings import ConfigurationError, Settings, UserSeed, load_settings

VALID_KEY = "k" * 32
USERS = [
    {"login": "anna", "password": "pw-anna", "company": "A"},
    {"login": "ivan", "password": "pw-ivan", "company": "A"},
    {"login": "petr", "password": "pw-petr", "company": "B"},
]


def make_environ(**overrides: str) -> dict[str, str]:
    environ = {"SECRET_KEY": VALID_KEY, "DASHBOARD_USERS": json.dumps(USERS)}
    environ.update(overrides)
    return environ


def load(environ: dict[str, str], env_file: Path | None = None) -> Settings:
    return load_settings(environ=environ, env_file=env_file)


def expect_error(environ: dict[str, str], variable: str, leaked_value: str | None = None) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load(environ)
    assert caught.value.variable == variable
    assert variable in str(caught.value)
    if leaked_value:
        assert leaked_value not in str(caught.value)


@pytest.mark.acceptance
def test_defaults_are_applied() -> None:
    settings = load(make_environ())
    assert settings.database_url == "sqlite:///data/dashboard.db"
    assert settings.database_path == (Path.cwd() / "data" / "dashboard.db").resolve()
    assert settings.timezone_name == "Asia/Ho_Chi_Minh"
    assert str(settings.timezone) == "Asia/Ho_Chi_Minh"
    assert settings.cookie_secure is False
    assert settings.weather_city == "Ho Chi Minh City"
    assert settings.weather_refresh_minutes == 30
    assert settings.rates_refresh_minutes == 15
    assert settings.secret_key == VALID_KEY


@pytest.mark.acceptance
def test_users_are_parsed_into_seeds() -> None:
    settings = load(make_environ())
    assert settings.dashboard_users == (
        UserSeed("anna", "pw-anna", "A"),
        UserSeed("ivan", "pw-ivan", "A"),
        UserSeed("petr", "pw-petr", "B"),
    )


@pytest.mark.acceptance
def test_explicit_values_override_defaults() -> None:
    settings = load(
        make_environ(
            DATABASE_URL="sqlite:///custom/app.db",
            TZ="Europe/Moscow",
            COOKIE_SECURE="true",
            WEATHER_CITY="Hanoi",
            WEATHER_REFRESH_MINUTES="5",
            RATES_REFRESH_MINUTES="7",
        )
    )
    assert settings.database_path == (Path.cwd() / "custom" / "app.db").resolve()
    assert settings.timezone_name == "Europe/Moscow"
    assert settings.cookie_secure is True
    assert settings.weather_city == "Hanoi"
    assert settings.weather_refresh_minutes == 5
    assert settings.rates_refresh_minutes == 7


@pytest.mark.acceptance
def test_absolute_database_path_is_kept(tmp_path: Path) -> None:
    target = tmp_path / "db" / "x.db"
    settings = load(make_environ(DATABASE_URL=f"sqlite:///{target.as_posix()}"))
    assert settings.database_path == target.resolve()


@pytest.mark.acceptance
def test_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    settings = load(make_environ(), env_file=tmp_path / "absent.env")
    assert settings.secret_key == VALID_KEY


@pytest.mark.acceptance
def test_env_file_supplies_values_when_environ_is_empty(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"SECRET_KEY={VALID_KEY}\nTZ=Europe/Moscow\n"
        f"DASHBOARD_USERS='{json.dumps(USERS)}'\nWEATHER_CITY=Da Nang\n",
        encoding="utf-8",
    )
    settings = load({}, env_file=env_file)
    assert settings.timezone_name == "Europe/Moscow"
    assert settings.weather_city == "Da Nang"
    assert len(settings.dashboard_users) == 3


@pytest.mark.acceptance
def test_environment_wins_over_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"SECRET_KEY={'f' * 40}\nTZ=Europe/Moscow\nDASHBOARD_USERS={json.dumps(USERS)}\n",
        encoding="utf-8",
    )
    settings = load({"SECRET_KEY": VALID_KEY, "TZ": "Asia/Tokyo"}, env_file=env_file)
    assert settings.secret_key == VALID_KEY
    assert settings.timezone_name == "Asia/Tokyo"
    assert len(settings.dashboard_users) == 3


@pytest.mark.acceptance
def test_env_file_comments_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"# comment\n\nSECRET_KEY={VALID_KEY}\nDASHBOARD_USERS={json.dumps(USERS)}\n",
        encoding="utf-8",
    )
    assert load({}, env_file=env_file).secret_key == VALID_KEY


@pytest.mark.acceptance
def test_secret_key_is_required() -> None:
    environ = make_environ()
    del environ["SECRET_KEY"]
    expect_error(environ, "SECRET_KEY")


@pytest.mark.acceptance
def test_secret_key_empty_is_rejected() -> None:
    expect_error(make_environ(SECRET_KEY=""), "SECRET_KEY")


@pytest.mark.acceptance
def test_secret_key_of_31_chars_is_rejected_without_leaking_value() -> None:
    value = "s3cretvalue" + "x" * 20
    assert len(value) == 31
    expect_error(make_environ(SECRET_KEY=value), "SECRET_KEY", value)


@pytest.mark.acceptance
def test_secret_key_of_32_chars_is_accepted() -> None:
    assert load(make_environ(SECRET_KEY="a" * 32)).secret_key == "a" * 32


@pytest.mark.acceptance
def test_secret_key_placeholder_is_rejected_without_leaking_value() -> None:
    expect_error(make_environ(SECRET_KEY="change-me"), "SECRET_KEY", "change-me")


@pytest.mark.acceptance
def test_dashboard_users_is_required() -> None:
    environ = make_environ()
    del environ["DASHBOARD_USERS"]
    expect_error(environ, "DASHBOARD_USERS")


@pytest.mark.acceptance
def test_dashboard_users_empty_is_rejected() -> None:
    expect_error(make_environ(DASHBOARD_USERS=""), "DASHBOARD_USERS")


@pytest.mark.acceptance
def test_dashboard_users_invalid_json_is_rejected_without_leaking_value() -> None:
    value = "not-json-topsecret"
    expect_error(make_environ(DASHBOARD_USERS=value), "DASHBOARD_USERS", value)


@pytest.mark.acceptance
def test_dashboard_users_object_instead_of_array_is_rejected() -> None:
    value = json.dumps({"login": "leakylogin", "password": "leakypw", "company": "c"})
    expect_error(make_environ(DASHBOARD_USERS=value), "DASHBOARD_USERS", "leakypw")


@pytest.mark.acceptance
def test_dashboard_users_non_object_element_is_rejected() -> None:
    expect_error(make_environ(DASHBOARD_USERS='["anna"]'), "DASHBOARD_USERS")


@pytest.mark.acceptance
@pytest.mark.parametrize("missing", ["login", "password", "company"])
def test_dashboard_users_missing_field_is_rejected(missing: str) -> None:
    user = {"login": "anna", "password": "leakypw", "company": "A"}
    del user[missing]
    expect_error(make_environ(DASHBOARD_USERS=json.dumps([user])), "DASHBOARD_USERS", "leakypw")


@pytest.mark.acceptance
@pytest.mark.parametrize("bad_value", ["", "   ", 5, None, ["x"]])
def test_dashboard_users_invalid_field_value_is_rejected(bad_value: object) -> None:
    user = {"login": "anna", "password": "pw", "company": bad_value}
    expect_error(make_environ(DASHBOARD_USERS=json.dumps([user])), "DASHBOARD_USERS")


@pytest.mark.acceptance
@pytest.mark.parametrize("value", ["postgres://secretvalue", "sqlite://x.db", "data/app.db", ""])
def test_database_url_wrong_prefix_is_rejected(value: str) -> None:
    expect_error(make_environ(DATABASE_URL=value), "DATABASE_URL", value or None)


@pytest.mark.acceptance
def test_database_url_without_path_is_rejected() -> None:
    expect_error(make_environ(DATABASE_URL="sqlite:///"), "DATABASE_URL")


@pytest.mark.acceptance
@pytest.mark.parametrize("value", ["Not/AZone_secret", "", "../../etc/passwd"])
def test_timezone_invalid_is_rejected(value: str) -> None:
    expect_error(make_environ(TZ=value), "TZ", value or None)


@pytest.mark.acceptance
def test_timezone_valid_name_is_accepted() -> None:
    assert str(load(make_environ(TZ="UTC")).timezone) == "UTC"


@pytest.mark.acceptance
@pytest.mark.parametrize("name", ["WEATHER_REFRESH_MINUTES", "RATES_REFRESH_MINUTES"])
@pytest.mark.parametrize("value", ["0", "1441", "abc", "-5", "1.5", "", "99999"])
def test_refresh_minutes_out_of_range_or_not_integer_is_rejected(name: str, value: str) -> None:
    expect_error(make_environ(**{name: value}), name, value if len(value) > 3 else None)


@pytest.mark.acceptance
@pytest.mark.parametrize("name", ["WEATHER_REFRESH_MINUTES", "RATES_REFRESH_MINUTES"])
def test_refresh_minutes_boundaries_are_accepted(name: str) -> None:
    attribute = name.lower()
    assert getattr(load(make_environ(**{name: "1"})), attribute) == 1
    assert getattr(load(make_environ(**{name: "1440"})), attribute) == 1440


@pytest.mark.acceptance
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("TRUE", True), ("True", True), ("false", False), ("FALSE", False)],
)
def test_cookie_secure_is_case_insensitive(raw: str, expected: bool) -> None:
    assert load(make_environ(COOKIE_SECURE=raw)).cookie_secure is expected


@pytest.mark.acceptance
@pytest.mark.parametrize("value", ["yes", "1", "0", "", "maybe"])
def test_cookie_secure_other_values_are_rejected(value: str) -> None:
    expect_error(make_environ(COOKIE_SECURE=value), "COOKIE_SECURE")


@pytest.mark.acceptance
def test_settings_is_frozen() -> None:
    settings = load(make_environ())
    with pytest.raises(AttributeError):
        settings.secret_key = "other"
