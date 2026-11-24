import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard import __version__
from dashboard.current_user import LoginRequiredError, require_user
from dashboard.database import connect, initialize_schema
from dashboard.login_attempts import LoginAttempts
from dashboard.routers.checklists import router as checklists_router
from dashboard.routers.login import router as login_router
from dashboard.session_cookie import SessionSigner
from dashboard.settings import Settings, load_settings
from dashboard.users import UserSeedError, seed_users

PACKAGE_DIRECTORY = Path(__file__).resolve().parent
LOGGER_NAME = "dashboard"
LOG_HANDLER_NAME = "dashboard-stdout"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOGIN_PATH = "/login"
HTMX_REQUEST_HEADER = "HX-Request"
HTMX_REDIRECT_HEADER = "HX-Redirect"

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


async def redirect_to_login(request: Request, error: Exception) -> Response:
    """Send an unauthenticated request to the login page, using HX-Redirect for HTMX requests."""
    if request.headers.get(HTMX_REQUEST_HEADER) == "true":
        return Response(status_code=200, headers={HTMX_REDIRECT_HEADER: LOGIN_PATH})
    return RedirectResponse(LOGIN_PATH, status_code=303)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application; without settings they are loaded from the environment."""
    configure_logging()
    resolved_settings = load_settings() if settings is None else settings

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        connection = connect(resolved_settings.database_path)
        try:
            initialize_schema(connection)
            try:
                seed_users(connection, resolved_settings.dashboard_users)
            except UserSeedError as error:
                logger.error("Запуск остановлен: %s", error)
                raise
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
        dependencies=[Depends(require_user)],
    )
    application.state.settings = resolved_settings
    application.state.database_path = resolved_settings.database_path
    application.state.login_attempts = LoginAttempts()
    application.state.session_signer = SessionSigner(resolved_settings.secret_key)
    application.add_exception_handler(LoginRequiredError, redirect_to_login)
    application.include_router(login_router)
    application.include_router(checklists_router)
    application.mount("/static", StaticFiles(directory=PACKAGE_DIRECTORY / "static"), name="static")

    @application.get("/health")
    async def read_health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return application
