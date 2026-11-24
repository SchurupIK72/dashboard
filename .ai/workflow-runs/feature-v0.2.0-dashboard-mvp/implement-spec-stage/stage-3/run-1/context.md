# Stage 3 shared context (Покупки и дела)

Repository: c:\Repo\Dashboard (Windows 11; branch feature/v0.2.0-dashboard-mvp; base_commit ba62a95c390c4942f9ea5744127f5814da7d1fe7). Spec: `.ai/specs/feature-v0.2.0-dashboard-mvp.md` — read stage 3 and requirements R17–R22, R45, R48. Product boundaries: `.ai/DECISIONS.md`. UI language: Russian. Stages 1–2 are committed and accepted; do NOT modify their files except those named in your allowed_files.

## Tools
- Run Python/uv through Bash with this prefix:
  `export PATH="/c/Users/SchurupIK/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"; cd /c/Repo/Dashboard`
  then `uv run ruff format <files>`, `uv run ruff check <files>`, `uv run python -c ...`, `timeout 150 uv run pytest <explicit paths> -q`.
- Never run a bare `uv run pytest` (always explicit paths), never `pip install`; dependencies only via `uv add` (none expected).
- Each command ≤150 s (`timeout 150`). No git write commands (no add/commit/checkout/stash); the main agent owns git.

## Code rules (binding)
- Python 3.12, full type hints incl. return types; no `Any`, no bare `except`, no star imports; imports as `from dashboard.module import Name`.
- NO comments in code at all; docstrings only on public API, one sentence. HTML/Jinja templates: no comments either.
- Names: modules by domain noun; classes PascalCase nouns; functions snake_case verbs; booleans is_/has_/can_/should_; exceptions end with `Error`; never `utils/helpers/common/manager/processor/base/core`.
- ruff line length 100; `ruff format --check` and `ruff check` must pass on touched .py files.
- SQL always parameterized (`?`); Jinja2 autoescape ON (never `|safe` on user data); data-changing routes POST only.
- Package root `src/dashboard/`; schema appended to `src/dashboard/schema.sql` (only `CREATE TABLE/INDEX IF NOT EXISTS`).
- Implementers write NO tests and never touch `tests/`. Acceptance testers write only under their `test_allowed_files`, mark every test `@pytest.mark.acceptance`, change no source code, put no comments in tests.

## Existing stage 1–2 facts (verified)
- `dashboard.main`: `create_app(settings)`, module-level `templates = Jinja2Templates(directory=…/templates)` (autoescape on), global dependency `require_user` (all routes except /login, /health need a session; unauthenticated → 303 /login, HTMX → 200 + `HX-Redirect: /login`), `application.include_router(login_router)` pattern. The router pattern in `dashboard/routers/login.py` imports `templates` lazily inside a function (`from dashboard.main import templates`) to avoid a circular import — follow it.
- `dashboard.database`: `connect(path)`, `initialize_schema(connection)`, `get_connection(request)` FastAPI dependency (per-request connection, `sqlite3.Row` rows). `schema.sql` currently has `app_meta`, `companies`, `users`.
- `dashboard.current_user.current_user(request) -> User`. Tests log in via `POST /login` with the form fields `login`, `password` and reuse the cookie (see `tests/acceptance/test_stage2_protection.py` for the app/settings builder pattern).
- `templates/base.html` defines blocks `title` and `content`; nav shown only if `current_user` is defined in the template context.

## Stage 3 contracts (fixed here so parallel items agree)

### Service `dashboard/services/checklist_items.py` (item C3.1)
- `class ChecklistKind(StrEnum)`: `SHOPPING = "shopping"`, `TODOS = "todos"`.
- `MAX_TITLE_LENGTH = 200`.
- `@dataclass(frozen=True) class ChecklistItem`: `id: int`, `kind: ChecklistKind`, `title: str`, `is_done: bool`, `created_at: str`, `done_at: str | None` (timestamps: ISO-8601 UTC strings with microseconds).
- `class InvalidTitleError(Exception)` (title empty after trim or longer than 200 chars); `class ChecklistItemNotFoundError(Exception)` (no item with this id in this kind).
- `add_item(connection, kind: ChecklistKind, title: str, now: datetime | None = None) -> ChecklistItem`
- `list_items(connection, kind: ChecklistKind) -> list[ChecklistItem]` ordered per R21: open items first by `created_at` ASC then `id` ASC; done items after them by `done_at` DESC then `id` DESC.
- `toggle_item(connection, kind, item_id: int, now: datetime | None = None) -> ChecklistItem` (sets/clears `is_done`, sets `done_at` when done, clears it when reopened)
- `rename_item(connection, kind, item_id: int, title: str) -> ChecklistItem`
- `delete_item(connection, kind, item_id: int) -> None`
- Title rule (R17): `title.strip()`, length 1–200 after trimming; the stored title is the trimmed one. Invalid → `InvalidTitleError`, nothing written. An id of another kind counts as not found (`ChecklistItemNotFoundError`). Every write commits.
- Table `checklist_items(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL CHECK (kind IN ('shopping','todos')), title TEXT NOT NULL, is_done INTEGER NOT NULL DEFAULT 0 CHECK (is_done IN (0, 1)), created_at TEXT NOT NULL, done_at TEXT)` plus an index on `(kind, is_done, created_at)`.
- `dashboard/services/__init__.py` (empty package marker) is created by C3.1.

### Templates (item C3.3)
- `checklist.html` extends `base.html`; context: `checklist_title: str` («Покупки» / «Дела»), `checklist_path: str` ("/shopping" / "/todos"), `items: Sequence[ChecklistItem]`, `error: str | None`. Block `title` = `checklist_title`; block `content` = `<h1>` with the title plus `{% include "_checklist_items.html" %}`.
- `_checklist_items.html` (fragment, no `<html>`): root `<div id="checklist-items">` containing: the error message (only when `error` is set, in an element with class `error`), the add form (`hx-post="{{ checklist_path }}/add"`, `hx-target="#checklist-items"`, `hx-swap="outerHTML"`, `method="post"`, `action="{{ checklist_path }}/add"`, text input `name="title"` with `maxlength="200"` and `required`, submit button «Добавить»), and a `<ul>` with one `<li>` per item in the given order. Per item: toggle form (POST `{{ checklist_path }}/{{ item.id }}/toggle`, same hx-* attributes; a checkbox-like button showing done state), the title (done → wrapped in `<s class="is-done">…</s>`, else plain text; autoescaped), rename form (POST `{{ checklist_path }}/{{ item.id }}/rename`, input `name="title"` prefilled with the current title, button «Сохранить»), delete form (POST `{{ checklist_path }}/{{ item.id }}/delete`, `hx-confirm="Удалить позицию?"` on the form or its button). Empty list → a short «Список пуст» line. All user-visible text Russian. Every form has both plain `method="post"`/`action` and the `hx-*` attributes (works without JS).

### Router `dashboard/routers/checklists.py` (item C3.2; wave 2)
- Exports `router: APIRouter`; `main.py` includes it. For each list (shopping: path `/shopping`, title «Покупки»; todos: path `/todos`, title «Дела») routes: `GET {path}` (full page `checklist.html`), `POST {path}/add` (form `title`), `POST {path}/{item_id}/toggle`, `POST {path}/{item_id}/rename` (form `title`), `POST {path}/{item_id}/delete`. No owner checks (R22). GET never mutates (R48); mutating routes exist only as POST (GET on them → 405).
- Response rules: request with header `HX-Request: true` → fragment `_checklist_items.html` rendered with the current list (status 200, also on invalid title or missing item — then with `error` set: «Название должно быть от 1 до 200 символов» / «Позиция не найдена»). Plain (non-HTMX) request: success → 303 to `{path}`; invalid title → full page `checklist.html` with `error`, status 422; missing item → 404.
