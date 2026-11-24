# Shared context for implementers and acceptance testers

Repository: c:\Repo\Dashboard (Windows 11; branch feature/v0.2.0-dashboard-mvp). Spec: `.ai/specs/feature-v0.2.0-dashboard-mvp.md` — read the requirement rows (R-IDs) named in your item and the «Архитектурные решения» table. Product boundaries: `.ai/DECISIONS.md`. Language of UI texts: Russian.

## Tools

- Run Python/uv through Bash with this prefix:
  `export PATH="/c/Users/SchurupIK/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"; cd /c/Repo/Dashboard`
  then `uv run ruff format <files>`, `uv run ruff check <files>`, `uv run python -c ...`, `uv run pytest <explicit paths> -q`.
- Never run a bare `uv run pytest` (always explicit paths), never `pip install`; add dependencies only with `uv add`.
- Each command must finish within 150 s; use `timeout 150`.
- Do not use git write commands (no add/commit/checkout/stash); the main agent owns git.

## Code rules (project rules, binding)

- Python 3.12, full type hints incl. return types; no `Any`, no bare `except`, no `from x import *`; imports as `from dashboard.module import Name`.
- NO comments in code at all (the release gate rejects narrative comments); docstrings only on public API, one sentence.
- Names: modules by domain noun; classes `PascalCase` nouns; functions `snake_case` verbs; booleans `is_/has_/can_/should_`; exceptions end with `Error`; collections plural. Do not name things `utils`, `helpers`, `common`, `manager`, `processor`, `base`, `core`.
- ruff: line length 100; code must pass `ruff format --check` and `ruff check`.
- SQL always parameterized (`?` placeholders); Jinja2 autoescape on; data-changing routes are POST only.
- Package root: `src/dashboard/` (import name `dashboard`); templates in `src/dashboard/templates/`, static files in `src/dashboard/static/`, schema in `src/dashboard/schema.sql`; `[tool.pytest.ini_options]` already has `pythonpath = ["src"]` and the `acceptance` marker.
- Touch ONLY the files in your item's allowed_files. If the work needs another file, stop and report instead of editing it.
- Implementers write NO tests and never touch `tests/`. Acceptance testers write only under `tests/`, mark every test `@pytest.mark.acceptance`, change no source code.

## Cross-stage interface contracts

Stage 1 (fixed here so parallel items agree):

- `dashboard/__init__.py`: `__version__: str = "0.2.0"`.
- `dashboard/settings.py`:
  - `class ConfigurationError(Exception)` with attribute `variable: str`; message contains the variable name and NEVER the variable value.
  - `@dataclass(frozen=True) class UserSeed: login: str; password: str; company: str`.
  - `@dataclass(frozen=True) class Settings` with fields: `database_url: str`, `database_path: Path` (resolved from `sqlite:///<path>`; a relative path is relative to the current working directory), `secret_key: str`, `timezone_name: str`, `timezone: ZoneInfo`, `dashboard_users: tuple[UserSeed, ...]`, `cookie_secure: bool`, `weather_city: str`, `weather_refresh_minutes: int`, `rates_refresh_minutes: int`.
  - `def load_settings(environ: Mapping[str, str] | None = None, env_file: Path | None = Path(".env")) -> Settings` — `environ=None` means `os.environ`; values from `environ` win over the `.env` file; a missing `env_file` is not an error.
  - Variables, defaults and validation: R3 and R47 of the spec (`SECRET_KEY` and `DASHBOARD_USERS` required; `SECRET_KEY` >= 32 chars and != `change-me`; `DATABASE_URL` default `sqlite:///data/dashboard.db` and must start with `sqlite:///`; `TZ` valid IANA name via `zoneinfo`; refresh minutes integers 1..1440; `COOKIE_SECURE` true/false case-insensitive; `DASHBOARD_USERS` JSON array of objects with non-empty string keys `login`, `password`, `company`).
  - Whether `DASHBOARD_USERS` has exactly 3 users and 2 companies is checked in stage 2, not in Settings.
- `dashboard/database.py`:
  - `def connect(database_path: Path) -> sqlite3.Connection` — creates the parent directory, opens with `check_same_thread=False`, `row_factory=sqlite3.Row`, executes `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`.
  - `def initialize_schema(connection: sqlite3.Connection) -> None` — executes the packaged `schema.sql` (all statements `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`), idempotent. Stage 1 schema contains only the table `app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)`; later stages append their tables to this same file.
- `dashboard/main.py`: `def create_app(settings: Settings | None = None) -> FastAPI` (`None` → `load_settings()`); lifespan opens the database, initializes the schema, stores `settings` and the database path in `app.state`, configures INFO logging to stdout; routes: `GET /health` → `{"status": "ok", "version": __version__}`; `/docs`, `/redoc`, `/openapi.json` disabled; static files mounted at `/static` from `src/dashboard/static`; module-level callable for uvicorn is used as `uvicorn dashboard.main:create_app --factory`. Templates are configured through a module-level `Jinja2Templates` (directory `src/dashboard/templates`, autoescape on) exposed as `dashboard.main.templates`.
- Templates: `base.html` defines blocks `title` and `content`, links `/static/app.css`, `/static/vendor/htmx.min.js`, `/static/vendor/chart.umd.min.js`, has `<meta name="viewport" content="width=device-width, initial-scale=1">`, `lang="ru"`, and a navigation placeholder rendered only when a template variable `current_user` is defined (stage 7 fills it).

Later stages will extend these contracts; stage packages restate what they consume.

## Report format (implementer)

Final message, brief: files changed/created (paths); what each public symbol does; commands run with real exit codes (ruff format --check, ruff check, an import/smoke run); assumptions or deviations from the contract; consumers/pins you searched for (grep of changed symbols in `src/` and `tests/`); open concerns. Do not paste long code or full tool output.
