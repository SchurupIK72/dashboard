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

## Stage 2 contracts (users and login)

NOTE: stage 1 is committed and accepted. `dashboard.settings` exports `ConfigurationError`, `UserSeed`, `Settings`, `load_settings` exactly as in the stage 1 contract above; do not change it. If `src/dashboard/settings.py` ever looks different from that contract, STOP and report it (an unknown actor rewrote it once during stage 1).

- `dashboard/passwords.py`:
  - `hash_password(password: str) -> str` — `hashlib.scrypt` n=16384, r=8, p=1, dklen=32, 16 random salt bytes (`secrets.token_bytes`), explicit `maxmem` (64 MiB); stored as `scrypt$16384$8$1$<salt_base64>$<hash_base64>` (standard `base64.b64encode`, ASCII).
  - `verify_password(password: str, stored_hash: str) -> bool` — parses the stored string and its parameters, recomputes, compares with `hmac.compare_digest`; any malformed stored string returns False (never raises).
  - `DUMMY_PASSWORD_HASH: str` — module-level hash of a random secret, used so unknown logins cost the same work as a wrong password.
- `dashboard/session_cookie.py`:
  - `SESSION_COOKIE_NAME = "dashboard_session"`, `SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60`.
  - `class SessionSigner`: `__init__(self, secret_key: str)`, `sign(self, user_id: int) -> str`, `read(self, token: str, max_age_seconds: int = SESSION_MAX_AGE_SECONDS) -> int | None` using `itsdangerous.URLSafeTimedSerializer` with a fixed salt; returns None for bad signature, expired, malformed or non-int payload (never raises).
  - `set_session_cookie(response: Response, token: str, secure: bool) -> None` (HttpOnly, SameSite=lax, Secure when `secure`, max_age SESSION_MAX_AGE_SECONDS, path `/`) and `clear_session_cookie(response: Response) -> None` (expires the cookie, same path).
- `dashboard/login_attempts.py`:
  - constants `MAX_FAILURES = 5`, `WINDOW_SECONDS = 300`, `BLOCK_SECONDS = 300`, `MAX_TRACKED_LOGINS = 1000`.
  - `class LoginAttempts`: `__init__(self, clock: Callable[[], float] = time.monotonic)`; `is_blocked(self, login: str) -> bool`; `register_failure(self, login: str) -> None`; `register_success(self, login: str) -> None`.
  - Rules (R16): failures are counted per entered login STRING as typed, including strings of non-existent logins; failures older than WINDOW_SECONDS are dropped; the 5th failure inside the window starts a block of BLOCK_SECONDS; attempts during a block do not extend it and do not add failures; success clears the login's counter; when more than MAX_TRACKED_LOGINS strings are tracked the entry with the oldest last activity that is NOT currently blocked is evicted first (a blocked entry is evicted only when no unblocked entry exists).
- `dashboard/database.py` (extend, keep stage 1 behavior): `get_connection(request: Request) -> Iterator[sqlite3.Connection]` — FastAPI dependency (a generator) that opens `connect(request.app.state.database_path)` per request and closes it afterwards.
- `dashboard/users.py` (tables appended to `schema.sql`, `CREATE TABLE IF NOT EXISTS`):
  - `companies(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)`; `users(id INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, company_id INTEGER NOT NULL REFERENCES companies(id))`.
  - `@dataclass(frozen=True) class Company: id: int; name: str`; `@dataclass(frozen=True) class User: id: int; login: str; company_id: int; company_name: str`.
  - `class UserSeedError(Exception)` — message names the offending login or rule, NEVER a password.
  - `seed_users(connection: sqlite3.Connection, seeds: Sequence[UserSeed]) -> None` (R10, Q21): seeds must be exactly 3 users with unique logins and exactly 2 distinct company names, else `UserSeedError`. If the `users` table is empty: create the companies (ids in order of first appearance in `seeds`) and the users (`hash_password`) in one transaction. If the table is not empty: the set of logins and each login→company mapping in `seeds` must equal the database, else `UserSeedError` naming the diverging login; passwords from `seeds` are ignored and existing hashes never change. Idempotent on repeated calls with the same seeds.
  - `authenticate(connection, login: str, password: str) -> User | None` — unknown login: run `verify_password(password, DUMMY_PASSWORD_HASH)` anyway and return None; wrong password None.
  - `get_user(connection, user_id: int) -> User | None`; `list_users(connection) -> list[User]` ordered by id; `list_companies(connection) -> list[Company]` ordered by id.
- `dashboard/routers/login.py` exposes `router: APIRouter`; `routers/__init__.py` is an empty package marker (no content). Routes: `GET /login` (200, form), `POST /login` (form fields `login`, `password`): blocked by `LoginAttempts` → 429 page text «Слишком много попыток входа. Повторите позже.»; unknown login or wrong password → `register_failure`, 401 page text «Неверный логин или пароль» (identical for both); success → `register_success`, 303 to `/` with the session cookie; `POST /logout` → 303 to `/login` with the cookie cleared. Collaborators come from `request.app.state.login_attempts: LoginAttempts` and `request.app.state.session_signer: SessionSigner`, cookie `secure` flag from `request.app.state.settings.cookie_secure`; the connection from `Depends(get_connection)`. Template `login.html` extends `base.html` (title «Вход»), form with `login`, `password` fields and a submit button, an error message area (class `error`), no `current_user` passed (so no navigation).
- `dashboard/current_user.py`: `class LoginRequiredError(Exception)`; `def require_user(request: Request, connection: sqlite3.Connection = Depends(get_connection)) -> None` — global dependency that skips the exact paths `/login` and `/health`; otherwise reads the cookie `SESSION_COOKIE_NAME`, resolves the user via `request.app.state.session_signer.read` + `get_user`, stores it in `request.state.user` or raises `LoginRequiredError`; `def current_user(request: Request) -> User` returns `request.state.user`.
- `dashboard/main.py`: `create_app` constructs `FastAPI(..., dependencies=[Depends(require_user)])`, creates `app.state.login_attempts = LoginAttempts()` and `app.state.session_signer = SessionSigner(settings.secret_key)`, includes the login router, calls `seed_users(connection, settings.dashboard_users)` in the lifespan after `initialize_schema` (a `UserSeedError` stops the startup), registers an exception handler for `LoginRequiredError`: ordinary request → `RedirectResponse("/login", status_code=303)`; request with header `HX-Request: true` → status 200, empty body, header `HX-Redirect: /login`. `/static/*` stays open (mounted app).
