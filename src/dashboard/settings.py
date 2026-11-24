import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DATABASE_URL_PREFIX = "sqlite:///"
DEFAULT_DATABASE_URL = "sqlite:///data/dashboard.db"
DEFAULT_TIMEZONE_NAME = "Asia/Ho_Chi_Minh"
DEFAULT_WEATHER_CITY = "Ho Chi Minh City"
DEFAULT_WEATHER_REFRESH_MINUTES = "30"
DEFAULT_RATES_REFRESH_MINUTES = "15"
FORBIDDEN_SECRET_KEY = "change-me"
MIN_SECRET_KEY_LENGTH = 32
MIN_REFRESH_MINUTES = 1
MAX_REFRESH_MINUTES = 1440
USER_FIELDS = ("login", "password", "company")


class ConfigurationError(Exception):
    """Raised when a configuration variable is missing or invalid."""

    def __init__(self, variable: str, reason: str) -> None:
        super().__init__(f"Переменная {variable}: {reason}")
        self.variable = variable


@dataclass(frozen=True)
class UserSeed:
    """A user to create at application start."""

    login: str
    password: str
    company: str


@dataclass(frozen=True)
class Settings:
    """Validated application configuration."""

    database_url: str
    database_path: Path
    secret_key: str
    timezone_name: str
    timezone: ZoneInfo
    dashboard_users: tuple[UserSeed, ...]
    cookie_secure: bool
    weather_city: str
    weather_refresh_minutes: int
    rates_refresh_minutes: int


def read_env_file(env_file: Path | None) -> dict[str, str]:
    """Parse simple KEY=VALUE lines of a .env file; a missing file gives an empty mapping."""
    if env_file is None or not env_file.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        values[key] = strip_quotes(value.strip())
    return values


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_secret_key(raw: str | None) -> str:
    name = "SECRET_KEY"
    if raw is None or raw == "":
        raise ConfigurationError(name, "обязательна, но не задана")
    if raw == FORBIDDEN_SECRET_KEY:
        raise ConfigurationError(name, "содержит значение-заглушку, задайте свой ключ")
    if len(raw) < MIN_SECRET_KEY_LENGTH:
        raise ConfigurationError(name, f"должна быть не короче {MIN_SECRET_KEY_LENGTH} символов")
    return raw


def parse_database_path(raw: str) -> Path:
    name = "DATABASE_URL"
    if not raw.startswith(DATABASE_URL_PREFIX):
        raise ConfigurationError(name, f"должна иметь вид {DATABASE_URL_PREFIX}<путь>")
    path_text = raw[len(DATABASE_URL_PREFIX) :]
    if not path_text.strip():
        raise ConfigurationError(name, "не содержит путь к файлу базы данных")
    return Path(path_text).resolve()


def parse_timezone(raw: str) -> ZoneInfo:
    name = "TZ"
    try:
        return ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ConfigurationError(
            name, "должна быть существующим именем часового пояса IANA"
        ) from None


def parse_refresh_minutes(name: str, raw: str) -> int:
    text = raw.strip()
    if not (text.isascii() and text.isdecimal()):
        raise ConfigurationError(name, "должна быть целым числом")
    minutes = int(text)
    if not MIN_REFRESH_MINUTES <= minutes <= MAX_REFRESH_MINUTES:
        raise ConfigurationError(
            name, f"должна быть от {MIN_REFRESH_MINUTES} до {MAX_REFRESH_MINUTES}"
        )
    return minutes


def parse_cookie_secure(raw: str) -> bool:
    lowered = raw.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ConfigurationError("COOKIE_SECURE", "должна быть true или false")


def parse_weather_city(raw: str) -> str:
    city = raw.strip()
    if not city:
        raise ConfigurationError("WEATHER_CITY", "не должна быть пустой")
    return city


def parse_dashboard_users(raw: str | None) -> tuple[UserSeed, ...]:
    name = "DASHBOARD_USERS"
    if raw is None or raw.strip() == "":
        raise ConfigurationError(name, "обязательна, но не задана")
    try:
        decoded: object = json.loads(raw)
    except ValueError:
        raise ConfigurationError(name, "должна быть корректным JSON") from None
    if not isinstance(decoded, list):
        raise ConfigurationError(name, "должна быть JSON-массивом объектов")
    users: list[UserSeed] = []
    for item in decoded:
        if not isinstance(item, dict):
            raise ConfigurationError(name, "каждый элемент массива должен быть объектом")
        fields: dict[str, str] = {}
        for field in USER_FIELDS:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ConfigurationError(
                    name, f"поле {field} каждого объекта должно быть непустой строкой"
                )
            fields[field] = value
        users.append(UserSeed(fields["login"], fields["password"], fields["company"]))
    return tuple(users)


def load_settings(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = Path(".env"),
) -> Settings:
    """Build validated settings from the environment and an optional .env file."""
    source = os.environ if environ is None else environ
    merged: dict[str, str] = {**read_env_file(env_file), **source}

    secret_key = parse_secret_key(merged.get("SECRET_KEY"))
    dashboard_users = parse_dashboard_users(merged.get("DASHBOARD_USERS"))
    database_url = merged.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    database_path = parse_database_path(database_url)
    timezone_name = merged.get("TZ", DEFAULT_TIMEZONE_NAME)
    timezone = parse_timezone(timezone_name)
    cookie_secure = parse_cookie_secure(merged.get("COOKIE_SECURE", "false"))
    weather_city = parse_weather_city(merged.get("WEATHER_CITY", DEFAULT_WEATHER_CITY))
    weather_refresh_minutes = parse_refresh_minutes(
        "WEATHER_REFRESH_MINUTES",
        merged.get("WEATHER_REFRESH_MINUTES", DEFAULT_WEATHER_REFRESH_MINUTES),
    )
    rates_refresh_minutes = parse_refresh_minutes(
        "RATES_REFRESH_MINUTES",
        merged.get("RATES_REFRESH_MINUTES", DEFAULT_RATES_REFRESH_MINUTES),
    )
    return Settings(
        database_url=database_url,
        database_path=database_path,
        secret_key=secret_key,
        timezone_name=timezone_name,
        timezone=timezone,
        dashboard_users=dashboard_users,
        cookie_secure=cookie_secure,
        weather_city=weather_city,
        weather_refresh_minutes=weather_refresh_minutes,
        rates_refresh_minutes=rates_refresh_minutes,
    )
