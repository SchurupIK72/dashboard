# Common package (stage-1, run-1) — applies to every item package

repo_root: C:/Repo/Dashboard
branch: feature/v0.2.0-dashboard-mvp
base_commit: ae69a4b3aace431beaa1ec76f520e7987e8f1200
spec_path: .ai/specs/feature-v0.2.0-dashboard-mvp.md  (read the item's requirements R## in section «Требования» and the stage section «Этап 1»)
stage_id: stage-1
user_decisions: []
accepted_materials: []

## Architecture constraints
- `.ai/DECISIONS.md`: one container, SQLite in volume, no frontend build (FastAPI + Jinja2/HTMX); external data cached; money is not moved.
- Python 3.12, FastAPI, SQLite (stdlib `sqlite3`), Jinja2, HTMX, Chart.js, uv, ruff (line-length 100).
- Source layout: `src/dashboard/` (package `dashboard`), `tests/`. `pyproject.toml` has `[tool.uv] package = false`; the package is imported via pytest `pythonpath = ["src"]` and, in the container, `PYTHONPATH=/app/src`.
- Rules: `.claude/rules/python-style.md` (type hints everywhere incl. return types; snake_case module names named after domain entities; no `Any`; no bare `except`; docstring only for public API, one sentence; no `utils/helpers/manager` names), `.claude/rules/docker-rules.md` for Dockerfile/compose.
- Tooling on this machine (Windows, Git Bash). Always prefix shell commands with:
  `export PATH="$APPDATA/Python/Python312/Scripts:/c/Users/SchurupIK/AppData/Local/Programs/Python/Python312:$PATH"`
  Use `uv` for everything (`uv run pytest`, `uv run ruff`, `uv add`). Never `pip install`.
- Comment cleanliness (hard gate): comments may reference decisions only as `D##` of `.ai/DECISIONS.md`. NO spec refs (`C1.2`, `R47`, `Q17`, «ТЗ», «этап N»), NO narrative comments, NO multi-line function descriptions, NO TODO/FIXME, NO debug leftovers. Prefer no comments at all. A one-sentence docstring on public API is allowed. This applies to test files as well.
- UI text is Russian.

## Time budget (time_budget)
Every command ≤ 150 s: `timeout 150 <cmd> > <output file> 2>&1` (no pipe), a process alive past 200 s is a hang — kill the tree, read the file. Never run a bare repo-wide `uv run pytest` — pass explicit paths.

## Roles
- Implementer: edits ONLY `allowed_files`; writes NO tests; no commit; does not touch the spec or checkboxes; no sub-agents. Needs a file outside `allowed_files` → report `blocked`. Reports in the 7-section format of its role file; detailed outputs go to `report_paths`. Preserve pre-existing dirty/untracked content (item_baseline).
- Acceptance tester: writes tests ONLY in `test_allowed_files` (under `tests/`), marker `@pytest.mark.acceptance` (register-neutral: use `pytestmark = pytest.mark.acceptance`), never edits source; 9-section report; evidence under `evidence_paths`.
- Parallel items of a wave run concurrently in the same working tree: ignore sibling files that are mid-flight; judge only your own area.

## Stage 1 definition of done (stage_definition_of_done)
`docker compose up` brings the app up; `/health` returns 200 with version `0.2.0`; double start on one DB passes; `ruff format --check` and `ruff check` are clean; every invalid config variable blocks start with its name.

## Pre-existing state (item_baseline summary)
The repo has ONLY infrastructure files untracked/unchanged: `pyproject.toml` (version 0.1.0, deps fastapi, uvicorn[standard], jinja2, httpx, python-multipart, itsdangerous; dev: pytest, pytest-cov, ruff, pre-commit, pyyaml, jsonschema, tiktoken==0.14.0; `[tool.uv] package=false`; `[tool.ruff]`, `[tool.pytest.ini_options] testpaths=["tests"]`), `uv.lock`, `.gitignore` (lists `.claude/settings.json`, `.claude/settings.local.json`, `.env`, `.venv/`, `__pycache__/`, `data/`), `scripts/`, `.ai/`, `.claude/`, `.agents/`, `.codex/`, `assets/`, `schemas/`, `templates/`. `src/` and `tests/` (except an empty `tests/acceptance/`) do not exist yet. `.venv` is already synced with `uv sync`. Do not modify anything outside your `allowed_files`.
