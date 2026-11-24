# Researcher package — C3.2

- repo_root: c:\Repo\Dashboard
- branch: feature/v0.2.0-dashboard-mvp
- base_commit: ba62a95c390c4942f9ea5744127f5814da7d1fe7 (working tree holds accepted, uncommitted C3.1 and C3.3 results)
- spec_path: .ai/specs/feature-v0.2.0-dashboard-mvp.md
- stage_id: stage-3 (Этап 3: Покупки и дела)
- checkbox_id: C3.2
- item_text: Реализовать маршруты `/shopping` и `/todos` и операции POST для обоих списков без проверки владельца позиции.
- requirements: R17, R18, R19, R20 (операции через маршруты), R22 (любой из трёх пользователей меняет любые позиции; нет владельца), R48 (изменения только POST; GET не меняет данные; изменяющие маршруты на GET → 405) — read the rows in the spec «Требования»; and R14 (all routes need a session, already provided by the global dependency).
- architecture_constraints: FastAPI + SQLite + Jinja2/HTMX; shared context and binding router contract — c:\Repo\Dashboard\.ai\workflow-runs\feature-v0.2.0-dashboard-mvp\implement-spec-stage\stage-3\run-1\context.md (READ FIRST; section «Router»). Accepted inputs: src/dashboard/services/checklist_items.py, src/dashboard/templates/checklist.html, src/dashboard/templates/_checklist_items.html (already in the working tree).
- allowed_files: src/dashboard/routers/checklists.py (new), src/dashboard/main.py (only the import and include_router of the new router)
- role: workflow-researcher; assigned_model: haiku
- user_decisions: []
- accepted_materials: [items/C3.1/implementer-report.md, items/C3.3/implementer-report.md, items/C3.1/acceptance/acceptance-report.md, items/C3.3/acceptance/acceptance-report.md]
- Consumer search required (by symbol/literal, not file name): existing tests that pin routes, `include_router`, HTMX handling or route sets (tests/acceptance/test_stage2_protection.py collects ALL application routes and requests each method without a cookie expecting 303 — check how path-parameter routes like `/shopping/{item_id}/toggle` behave in that test and whether a route-with-path-param request without cookie is still 303 via the global dependency); how FastAPI handles `HX-Request` header reads; how to register the same handlers for two kinds (paths /shopping, /todos) without duplicate code; HTTP 405 behavior for GET on POST-only paths (note: a GET on `/shopping/1/toggle` has no GET route → 405 expected; with the global dependency it may be 303 first when unauthenticated — report what happens).
- Report applicable UI/slow/integration layers with justified exclusions.
