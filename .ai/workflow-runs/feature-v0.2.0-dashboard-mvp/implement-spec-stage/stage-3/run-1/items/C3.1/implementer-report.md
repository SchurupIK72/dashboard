### Result
Item: C3.1
Verdict: implemented
Blocked reason: N/A

### Research
| File and symbol | Relevant contract/pattern | Consequence for the solution |
|---|---|---|
| src/dashboard/users.py | frozen dataclass, `_to_user` row mapper with casts, parameterized execute, `*Error` exceptions, lastrowid None guard | Same structure in checklist_items.py |
| src/dashboard/schema.sql | `IF NOT EXISTS` statements, 4-space indent, no comments; run on every start via executescript | Table and index appended with IF NOT EXISTS |
| context.md, section Service | fixed public contract | Names, signatures, ordering implemented as specified |

### Changed Files
| File | Change |
|---|---|
| src/dashboard/schema.sql | appended table checklist_items and index idx_checklist_items_kind_state (kind, is_done, created_at) |
| src/dashboard/services/__init__.py | new, empty |
| src/dashboard/services/checklist_items.py | new: ChecklistKind, MAX_TITLE_LENGTH, ChecklistItem, InvalidTitleError, ChecklistItemNotFoundError, add_item, list_items, toggle_item, rename_item, delete_item |

### Solution Summary
Per accepted research and binding decisions: title validated (strip, 1..200) before any SQL, including in rename before lookup; naive now treated as UTC, aware converted to UTC, isoformat microseconds; every query filters by id AND kind.value; every write commits; toggle sets or clears is_done/done_at and re-reads the item; list_items concatenates open (created_at, id ASC) and done (done_at, id DESC) queries. No public contract change versus context.md.

### Criteria Mapping
| Requirement / criterion | Where implemented | Existing check or pending verification |
|---|---|---|
| R17 add, trimmed 1-200, invalid rejected | add_item, _validate_title | smoke OK; acceptance tests pending |
| R18 toggle, persisted | toggle_item | smoke OK (reopen to clear done_at, persistence across reconnect) |
| R19 rename, same rules, old title kept | rename_item | smoke OK |
| R20 delete | delete_item | smoke OK |
| R21 ordering (contract) | list_items | smoke OK |

### Checks
| Command | Exit code | Result |
|---|---|---|
| uv run ruff format --check services/checklist_items.py services/__init__.py | 0 | pass |
| uv run ruff check same files | 0 | pass |
| smoke (PYTHONPATH=src uv run python script: connect, initialize_schema twice, add/list/toggle/rename/delete, kind isolation, invalid titles, tz conversion, persistence) | 0 | SMOKE OK; output in items/C3.1/smoke.txt (first run exit 1 was a Windows temp-dir cleanup error from an unclosed connection in the throwaway script, assertions had passed; rerun clean) |

### Open Questions
- None
