### Result
Item: C3.2
Verdict: implemented
Blocked reason: N/A

### Research
| File and symbol | Relevant contract/pattern | Consequence for the solution |
|---|---|---|
| src/dashboard/routers/login.py `_render_login` | Lazy `from dashboard.main import templates` inside a function avoids the circular import | Same lazy import of `HTMX_REQUEST_HEADER` and `templates` in checklists.py |
| src/dashboard/main.py `create_app`, `require_user` | Global dependency guards every route; `HTMX_REQUEST_HEADER` constant exists; routers included without prefix | One import line (before the login import) and one `include_router` line after the login one; full literal paths in the decorators |
| src/dashboard/services/checklist_items.py | `add_item`/`toggle_item`/`rename_item`/`delete_item`/`list_items`; `InvalidTitleError`, `ChecklistItemNotFoundError`; `MAX_TITLE_LENGTH`; the service commits | Router only maps results and errors to responses; the error text is built from `MAX_TITLE_LENGTH` |
| context.md section «Router» | GET full page; POST add/toggle/rename/delete; HTMX → fragment 200; plain → 303/422/404 | `_render_checklist` and `_respond_after_change` implement the matrix |
| tests/acceptance/test_stage2_protection.py | The all-routes test requests every `route.path` without a cookie and expects 303 | The new routes stay behind the global dependency; the test is green |

### Changed Files
| File | Change |
|---|---|
| src/dashboard/routers/checklists.py | New: `Checklist` dataclass, `CHECKLISTS`, `router`, `_render_checklist`, `_respond_after_change`, `_register` (GET and 4 POST routes for `/shopping` and `/todos`) |
| src/dashboard/main.py | One import line and one `include_router(checklists_router)` line |

### Solution Summary
One module serves both lists. `_register` runs in a loop over `CHECKLISTS` and defines closures decorated with `router.get(path)` and `router.post(f"{path}/add")`, `/{item_id}/toggle`, `/rename` and `/delete`; route names are unique (`name=`). Handlers are sync, take `item_id: int` (a non-integer id gives the default 422) and `title: Form() = ""`, so a missing field gives an invalid-title response. They never read `request.state.user` (R22). GET only calls `list_items` (R48); the mutating paths are POST only, so GET on them returns 405. `_respond_after_change` runs the service call and maps the outcome. Success → HTMX 200 fragment, or plain 303 to `{path}`. `InvalidTitleError` → HTMX 200 fragment with `error`, or plain full page 422. `ChecklistItemNotFoundError` → HTMX 200 fragment with `error`, or plain full page 404. `current_user` is not passed to the templates. No public contract changed.

### Criteria Mapping
| Requirement / criterion | Where implemented | Existing check or pending verification |
|---|---|---|
| R17-R20 operations reachable | add/toggle/rename/delete routes in `_register` | smoke script (51 OK) |
| R22 no owner check | handlers do not use the user; vera toggles an item created by anna | smoke "other user toggles any item 303" |
| R48 POST only; GET never mutates | `router.post` for mutations; GET only lists | smoke: GET on add/toggle/rename/delete → 405 |
| R14 login required | global `require_user` | stage-2 all-routes test (green); smoke anon → 303 |
| HTMX/plain matrix | `_render_checklist`, `_respond_after_change` | smoke: fragments without `<html`, 422/404 pages, 200 + error for HTMX |
| Acceptance tests for the stage | not written by the implementer | pending, written by the tester role |

### Checks
| Command | Exit code | Result |
|---|---|---|
| `uv run ruff format --check src/dashboard/routers/checklists.py src/dashboard/main.py` | 0 | 2 files already formatted |
| `uv run ruff check src/dashboard/routers/checklists.py src/dashboard/main.py` | 0 | All checks passed |
| `PYTHONPATH=src uv run python items/C3.2/smoke.py` | 0 | 51 OK, no FAIL (output in items/C3.2/smoke-output.txt) |
| `timeout 150 uv run pytest tests/acceptance/test_stage2_protection.py tests/acceptance/test_stage2_login.py tests/acceptance/test_stage1_app.py -q` | 0 | 77 passed, 1 warning (output in items/C3.2/pytest-output.txt) |

### Open Questions
- None
