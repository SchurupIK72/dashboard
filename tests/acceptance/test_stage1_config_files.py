import re
from pathlib import Path

import pytest
import yaml

from dashboard.settings import ConfigurationError, load_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_VARIABLES = [
    "DATABASE_URL",
    "SECRET_KEY",
    "TZ",
    "COOKIE_SECURE",
    "WEATHER_CITY",
    "WEATHER_REFRESH_MINUTES",
    "RATES_REFRESH_MINUTES",
    "DASHBOARD_USERS",
]


def read_text(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def load_compose() -> dict[str, object]:
    document = yaml.safe_load(read_text("docker-compose.yml"))
    assert isinstance(document, dict)
    return document


def load_service() -> dict[str, object]:
    services = load_compose()["services"]
    assert isinstance(services, dict)
    assert len(services) >= 1
    service = next(iter(services.values()))
    assert isinstance(service, dict)
    return service


@pytest.mark.acceptance
@pytest.mark.parametrize("name", ["Dockerfile", "docker-compose.yml"])
def test_container_files_do_not_use_latest_tag(name: str) -> None:
    assert ":latest" not in read_text(name).lower()


@pytest.mark.acceptance
def test_dockerfile_images_are_pinned_to_explicit_tags() -> None:
    text = read_text("Dockerfile")
    base_images = re.findall(r"^FROM\s+(\S+)", text, flags=re.MULTILINE)
    copied_images = re.findall(r"--from=(\S+)", text)
    assert base_images
    for image in base_images + copied_images:
        assert re.search(r":[^/:]+$", image), image


@pytest.mark.acceptance
@pytest.mark.parametrize("name", ["Dockerfile", "docker-compose.yml"])
def test_container_files_have_no_workers_flag(name: str) -> None:
    assert "--workers" not in read_text(name)


@pytest.mark.acceptance
def test_compose_declares_named_volume_dashboard_data() -> None:
    volumes = load_compose()["volumes"]
    assert isinstance(volumes, dict)
    assert "dashboard-data" in volumes


@pytest.mark.acceptance
def test_compose_mounts_named_volume_at_app_data() -> None:
    mounts = load_service()["volumes"]
    assert isinstance(mounts, list)
    assert "dashboard-data:/app/data" in mounts


@pytest.mark.acceptance
def test_compose_has_no_host_directory_bind_mount() -> None:
    mounts = load_service().get("volumes", [])
    assert isinstance(mounts, list)
    for mount in mounts:
        source = str(mount).split(":", 1)[0]
        assert not source.startswith((".", "/", "~"))
        assert not re.match(r"^[A-Za-z]:[\\/]", str(mount))
        assert source == "dashboard-data"


@pytest.mark.acceptance
def test_compose_has_healthcheck_against_health_endpoint() -> None:
    healthcheck = load_service()["healthcheck"]
    assert isinstance(healthcheck, dict)
    assert healthcheck["test"]
    assert "/health" in str(healthcheck["test"])


@pytest.mark.acceptance
def test_compose_runs_without_extra_server_workers_in_command() -> None:
    service = load_service()
    assert "--workers" not in str(service.get("command", ""))
    assert "--workers" not in str(service.get("entrypoint", ""))


@pytest.mark.acceptance
def test_gitignore_excludes_env_file_and_data_directory() -> None:
    lines = [line.strip() for line in read_text(".gitignore").splitlines()]
    assert ".env" in lines
    assert "data/" in lines


@pytest.mark.acceptance
def test_env_example_defines_every_variable() -> None:
    keys = {
        line.partition("=")[0].strip()
        for line in read_text(".env.example").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    assert set(REQUIRED_VARIABLES) <= keys


@pytest.mark.acceptance
def test_env_example_fails_validation_on_secret_key() -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(environ={}, env_file=REPO_ROOT / ".env.example")
    assert caught.value.variable == "SECRET_KEY"


@pytest.mark.acceptance
def test_env_example_loads_once_secret_key_is_set(tmp_path: Path) -> None:
    lines = read_text(".env.example").splitlines()
    replaced = [
        "SECRET_KEY=" + "z" * 40 if line.startswith("SECRET_KEY=") else line for line in lines
    ]
    assert replaced != lines
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(replaced) + "\n", encoding="utf-8")
    settings = load_settings(environ={}, env_file=env_file)
    assert len(settings.dashboard_users) == 3
    assert len({user.company for user in settings.dashboard_users}) == 2
    assert settings.timezone_name == "Asia/Ho_Chi_Minh"
    assert settings.cookie_secure is False
    assert settings.weather_refresh_minutes == 30
    assert settings.rates_refresh_minutes == 15
