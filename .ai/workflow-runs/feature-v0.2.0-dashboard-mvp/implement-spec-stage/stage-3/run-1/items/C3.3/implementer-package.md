# Implementer package — C3.3

- repo_root: c:\Repo\Dashboard
- branch: feature/v0.2.0-dashboard-mvp
- base_commit: ba62a95c390c4942f9ea5744127f5814da7d1fe7
- item_baseline: clean tree at base_commit apart from untracked run/ownership files; both allowed files do not exist yet (see run-1/baseline-status.txt)
- spec_path: .ai/specs/feature-v0.2.0-dashboard-mvp.md
- stage_id: stage-3 (Этап 3: Покупки и дела)
- checkbox_id: C3.3
- item_text: Создать шаблоны страницы и фрагмента списка с порядком, зачёркиванием выполненных, HTMX-заменой фрагмента и `hx-confirm` на удалении.
- requirements: R21 (items rendered in the given order; done items struck through; list changes via HTMX fragment swap; fragment has no `<html>`), R20 (delete asks confirmation: `hx-confirm` present), R45 (autoescape ON, no `|safe`; `<script>alert(1)</script>` title rendered escaped)
- architecture_constraints: shared context and binding contract — c:\Repo\Dashboard\.ai\workflow-runs\feature-v0.2.0-dashboard-mvp\implement-spec-stage\stage-3\run-1\context.md (READ FIRST; section «Templates»). No CDN, no `<script>`, no `http(s)://` in the templates. The template does NOT re-sort items: order comes from the service (C3.1).
- allowed_files: src/dashboard/templates/checklist.html (new), src/dashboard/templates/_checklist_items.html (new)
- role: workflow-implementer; assigned_model: sonnet — medium: coordinated templates forming a contract with the wave-2 router, HTMX attributes, escaping
- dependencies: []
- check_commands: smoke render via `uv run python -c` using `dashboard.main.templates` (or Jinja2 Environment with `select_autoescape` over `src/dashboard/templates`) with `SimpleNamespace(id, title, is_done)` items including a title `<script>alert(1)</script>`: expect escaped output, `<s class="is-done">` only for done items, `hx-confirm="Удалить позицию?"` present, fragment (rendered alone) has no `<html`/`<!doctype`/`<body`, empty list shows «Список пуст»; regression `timeout 150 uv run pytest tests/acceptance/test_stage1_templates.py tests/acceptance/test_stage1_app.py -q` → all pass
- time_budget: one command ≤ 150 s (`timeout 150`, output to a file, no pipe)
- report_paths: .ai/workflow-runs/feature-v0.2.0-dashboard-mvp/implement-spec-stage/stage-3/run-1/items/C3.3/implementer-report.md (your final message is the report; save detailed outputs under items/C3.3/)
- user_decisions: []
- accepted_materials: [run-1/context.md]

## research_report (accepted, condensed)
- Reference: `templates/login.html` — `extends "base.html"`, blocks `title`/`content`, `<section class="login">` wrapper, `{% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}`, forms with plain `method="post"` and `action`, Russian text, no comments. htmx 2.0.4 is loaded by base.html.
- `checklist.html`: extends base; `title` block = `{{ checklist_title }}`; `content` block: `<section class="checklist">`, `<h1>{{ checklist_title }}</h1>` OUTSIDE the swapped root, then `{% include "_checklist_items.html" %}` (include shares context; no `with`).
- `_checklist_items.html`: root `<div id="checklist-items">`; first the `.error` paragraph (when `error`); add form (`method="post" action="{{ checklist_path }}/add" hx-post=… hx-target="#checklist-items" hx-swap="outerHTML"`, input `name="title" maxlength="200" required aria-label="Название"`, button «Добавить»); `{% if items %}<ul class="checklist-list">` one `<li>` per item (class `is-done` on `<li>` only when done) else `<p class="muted">Список пуст</p>`.
- Per item: toggle form (button `class="secondary"`, `aria-pressed`, `aria-label` «Вернуть в список»/«Отметить выполненным», shows ✓ when done else ○); title `<s class="is-done">{{ item.title }}</s>` when done else `<span>{{ item.title }}</span>`; rename form (input `name="title" value="{{ item.title }}" maxlength="200" required aria-label="Новое название"`, button «Сохранить» `class="secondary"`); delete form with `hx-confirm="Удалить позицию?"` on the `<form>` ONLY (htmx reads it from the issuing element), button «Удалить» `class="danger"`.
- No per-item `id` attributes (they would repeat). No `|safe`. No comments. No CSS edits (app.css is outside allowed files; existing `.error .muted button.secondary button.danger` suffice; `<s>` is struck by default).
- Existing tests do not scan the templates directory or other templates; no pins affected.
