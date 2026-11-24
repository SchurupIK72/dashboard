import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard import __version__
from dashboard.database import connect, initialize_schema
from dashboard.settings import Settings, load_settings

PACKAGE_DIRECTORY = Path(__file__).resolve().parent
LOGGER_NAME = "dashboard"
LOG_HANDLER_NAME = "dashboard-stdout"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

templates = Jinja2Templates(directory=PACKAGE_DIRECTORY / "templates")

logger = logging.getLogger(LOGGER_NAME)


def configure_logging() -> None:
    """Send INFO records of the dashboard logger to stdout, adding the handler only once."""
    logger.setLevel(logging.INFO)
    if any(handler.get_name() == LOG_HANDLER_NAME for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(LOG_HANDLER_NAME)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application; without settings they are loaded from the environment."""
    configure_logging()
    resolved_settings = load_settings() if settings is None else settings

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        connection = connect(resolved_settings.database_path)
        try:
            initialize_schema(connection)
            logger.info(
                "Запуск дашборда: версия %s, база данных %s, часовой пояс %s",
                __version__,
                resolved_settings.database_path,
                resolved_settings.timezone_name,
            )
            yield
        finally:
            connection.close()

    application = FastAPI(
        title="Dashboard",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database_path = resolved_settings.database_path
    application.mount("/static", StaticFiles(directory=PACKAGE_DIRECTORY / "static"), name="static")

    @application.get("/health")
    async def read_health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return application
