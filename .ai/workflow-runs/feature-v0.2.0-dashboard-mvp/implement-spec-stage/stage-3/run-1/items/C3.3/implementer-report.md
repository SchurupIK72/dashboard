### Result
Item: C3.3
Verdict: implemented
Blocked reason: N/A

### Research
| File and symbol | Relevant contract/pattern | Consequence for the solution |
|---|---|---|
| src/dashboard/templates/login.html | extends base.html, blocks title/content, section wrapper, `.error` paragraph, plain method/action forms, no comments | Same structure for checklist.html |
| src/dashboard/templates/base.html (blocks title, content; htmx loaded) | Provides blocks, htmx | No script/CDN in new templates |
| run-1/context.md section Templates | Binding contract for context vars and form routes | Followed literally |
| dashboard.main.templates | Jinja2Templates, autoescape on | Smoke render uses it; no `|safe` |

### Changed Files
| File | Change |
|---|---|
| src/dashboard/templates/checklist.html | New: page, extends base, h1 outside swapped root, includes fragment |
| src/dashboard/templates/_checklist_items.html | New: fragment root `#checklist-items` with error, add form, list or «Список пуст» |
| items/C3.3/smoke_render.py, smoke_output.txt, pytest_output.txt | Run artifacts (outside src) |

### Solution Summary
Fragment root div id="checklist-items" holds the error paragraph, the add form, and a ul with one li per item in the supplied order (no re-sort). Every form has method/action plus hx-post/hx-target="#checklist-items"/hx-swap="outerHTML". Done items: li class is-done and `<s class="is-done">`; open items: span. Delete form carries `hx-confirm="Удалить позицию?"`. Toggle button has aria-pressed/aria-label and shows ✓ or ○. No comments, no per-item ids, no `|safe`. No contract changes.

### Criteria Mapping
| Requirement / criterion | Where implemented | Existing check or pending verification |
|---|---|---|
| R21 order, strikethrough, HTMX swap, fragment without html | `_checklist_items.html` | Smoke: order, s_done_once, frag_no_html OK |
| R20 hx-confirm on delete | delete form | Smoke: confirm OK |
| R45 escaping | `{{ item.title }}` autoescaped | Smoke: escaped OK |
| Empty list | `<p class="muted">Список пуст</p>` | Smoke: empty OK |

### Checks
| Command | Exit code | Result |
|---|---|---|
| PYTHONPATH=src uv run python items/C3.3/smoke_render.py | 0 | all 10 checks True (first run exit 1 only because PYTHONPATH was missing) |
| timeout 150 uv run pytest tests/acceptance/test_stage1_templates.py tests/acceptance/test_stage1_app.py -q | 0 | 37 passed |

### Open Questions
- None
