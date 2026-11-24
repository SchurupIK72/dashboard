# Implementer package — C3.1

- repo_root: c:\Repo\Dashboard
- branch: feature/v0.2.0-dashboard-mvp
- base_commit: ba62a95c390c4942f9ea5744127f5814da7d1fe7
- item_baseline: clean tree at base_commit apart from untracked run/ownership files; sha256 of existing allowed file: src/dashboard/schema.sql = 7315e10e1b96fa2707e52627ae3ee01f19cf6d82eb9fdecd8acef692dcb5c96c (see run-1/baseline-hashes.txt). services/ does not exist yet.
- spec_path: .ai/specs/feature-v0.2.0-dashboard-mvp.md
- stage_id: stage-3 (Этап 3: Покупки и дела)
- checkbox_id: C3.1
- item_text: Создать таблицу `checklist_items` (вид списка, название, признак выполнения, время добавления, время отметки) и операции добавления, отметки, переименования, удаления с проверкой названия.
- requirements: R17 (add; title trimmed 1–200 chars, invalid rejected, list unchanged), R18 (toggle on/off, state persisted), R19 (rename with R17 rules, old title kept on error), R20 (delete)
- architecture_constraints: shared context and binding contract — c:\Repo\Dashboard\.ai\workflow-runs\feature-v0.2.0-dashboard-mvp\implement-spec-stage\stage-3\run-1\context.md (READ FIRST; section «Service»). DECISIONS.md: SQLite, no frontend build.
- allowed_files: src/dashboard/services/checklist_items.py (new), src/dashboard/services/__init__.py (new, empty), src/dashboard/schema.sql (append only)
- role: workflow-implementer; assigned_model: sonnet / effort default — medium: new local logic with clear solution, public contract consumed by wave 2, no complex signs
- dependencies: []
- check_commands: `uv run ruff format --check <touched .py>` → exit 0; `uv run ruff check <touched .py>` → exit 0; smoke: in a temp dir `connect` + `initialize_schema` twice, then add/list/toggle/rename/delete via `uv run python -c` → expected behaviors per contract
- time_budget: one command ≤ 150 s (`timeout 150`, output to a file, no pipe)
- report_paths: .ai/workflow-runs/feature-v0.2.0-dashboard-mvp/implement-spec-stage/stage-3/run-1/items/C3.1/implementer-report.md (your final message is the report; save command outputs under items/C3.1/)
- user_decisions: []
- accepted_materials: [run-1/context.md]
- decisions on researcher unknowns (binding): a naive `now` is treated as UTC (`replace(tzinfo=UTC)`), aware values are converted with `astimezone(UTC)`; timestamps always `isoformat(timespec="microseconds")`; `rename_item` validates the title BEFORE looking up the item; index name `idx_checklist_items_kind_state`; use `kind.value` as SQL parameter; every query filters by `id` AND `kind`.

## research_report (accepted, condensed)
- Edit sites: schema.sql append after the `users` table (4-space column indent, blank line between statements, no SQL comments); new `src/dashboard/services/__init__.py` (empty, like routers/__init__.py) and `services/checklist_items.py`.
- Reference pattern: `src/dashboard/users.py` — frozen dataclass + `_to_user` row mapper with explicit casts, parameterized `connection.execute`, exception ending in `Error`, one-sentence docstrings on public API only, private helpers without docstrings, `cursor.lastrowid` guarded against None.
- Structure: `_validate_title` (strip, 1..MAX_TITLE_LENGTH else InvalidTitleError), `_timestamp(now)`, `_to_item(row)`, `_find_item(connection, kind, item_id)` (raises ChecklistItemNotFoundError); public `add_item`, `list_items`, `toggle_item`, `rename_item`, `delete_item`; every write ends with `connection.commit()`; validate before any SQL.
- list_items order: open → `created_at ASC, id ASC`; done → `done_at DESC, id DESC` (two queries concatenated is acceptable).
- toggle: not done → `is_done=1, done_at=<ts>`; done → `is_done=0, done_at=NULL`; return re-read item.
- `initialize_schema` runs `executescript` on every start, so `IF NOT EXISTS` on table and index is mandatory. No existing test pins the table set.
- Do NOT touch tests/. No comments in code.
