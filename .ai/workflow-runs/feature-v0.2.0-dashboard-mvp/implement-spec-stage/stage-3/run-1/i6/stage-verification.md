# Stage 3 verification (I6)

Resumed run-1 on a second machine (macOS, Python 3.12.16); items C3.1–C3.3 were accepted in commit 539c0c6.

Stage-local set: stage-3 acceptance (items, routes, templates) + stage-2 protection/login + stage-1 app/database — 297 passed (pytest-stage-local.txt). ruff format --check / ruff check on src and tests clean. validate_stage_completion.py PASS.

Chain input → result → consumer:
- service checklist_items (C3.1) → router checklists.py renders page/fragment via templates (C3.3) → router included in create_app (main.py:93).
- DoD «add/toggle/rename/delete in both lists»: routes suite, both kinds parametrized.
- DoD «order per R21»: service + routes + template ordering tests.
- DoD «user 1's items changed by user 3»: test_item_added_by_first_user_is_changed_by_third_user_in_both_lists.
- DoD «changes only via POST»: test_get_on_mutating_routes_returns_405_and_does_not_change_database.

Not proven here: browser-level HTMX behaviour (hx-confirm dialog, fragment swap in a real browser) — left to write-tests UI scenario.
Note: checklist_items.py builds SQL with an f-string over a module constant (no user data) — R45 code search in stage 7 may flag it.
