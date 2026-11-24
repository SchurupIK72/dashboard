### Result
Item: C3.3
Verdict: passed
Blocked reason: N/A

### Acceptance Matrix
| Criterion | Independent expected result and source | Evidence | Status |
|---|---|---|---|
| R21 order | Fragment renders items in the order received and does not re-sort (done-first, reversed inputs keep input order); sorting itself is deferred to C3.1 | test_fragment_keeps_given_order_and_does_not_resort, test_fragment_order_follows_input_for_reversed_input | PASS |
| R21 strikethrough | Done items inside `<s class="is-done">`, open items in plain `<span>`, no `<s>` when all open | test_done_items_are_struck_through_and_open_items_are_not, test_all_open_items_have_no_strikethrough_element, test_done_toggle_button_reflects_state | PASS |
| R21 HTMX swap | Every form has method=post, action, hx-post equal to action, hx-target=#checklist-items, hx-swap=outerHTML, for /shopping and /todos | test_every_form_has_post_action_and_htmx_attributes[2] | PASS |
| R21 fragment has no html | No html/head/body/doctype; root div id=checklist-items; page contains the fragment once | test_fragment_has_no_html_document_and_has_root_container[2], test_page_extends_base_with_title_heading_and_fragment[2] | PASS |
| R20 hx-confirm | Each delete form has hx-confirm="Удалить позицию?", only delete forms have it | test_delete_form_requires_confirmation[2], test_confirmation_is_only_on_delete_forms | PASS |
| R20 POST only | All forms method=post; no hx-get/put/delete/patch, no links, no GET forms | test_no_get_based_htmx_or_links_to_mutating_routes | PASS |
| R45 escaping | `<script>alert(1)</script>` escaped in text (open and done) and in rename value; quote break-out and error text escaped; page has only src scripts | test_title_is_escaped_in_text_and_rename_value_for_open_item, test_title_is_escaped_for_done_item, test_title_with_quote_cannot_break_out_of_rename_value, test_error_text_is_escaped, test_page_escapes_hostile_title_and_adds_no_inline_script | PASS |
| Contract: empty/error/inputs | «Список пуст» only when empty; `.error` p only when error set; name=title, maxlength=200, required; Russian labels | test_empty_list_*, test_non_empty_list_hides_empty_message, test_no_error_element_*, test_error_is_shown_in_error_paragraph_inside_root, test_title_inputs_are_limited_required_and_named_title, test_button_labels_are_russian | PASS |
| Contract: no script/URL/comments | Sources and rendered output free of script, comments, URLs, |safe | test_fragment_contains_no_script_comment_or_external_url, test_template_sources_have_no_script_comments_or_urls[2] | PASS |

### Formal Audit
| Gate | Checks | Evidence | Status |
|---|---|---|---|
| F1 boundaries | Only the two new templates changed; my only write is tests/acceptance/test_stage3_checklist_templates.py; no source edits by me | git status: both templates untracked, one new test file | PASS |
| F2 requirements | R20, R21 (template side), R45 proven in the matrix | matrix | PASS |
| F3 contract compatibility | Markup matches context.md «Templates» (ids, hx-*, field names, texts, extends base.html, blocks title/content) | tests above | PASS |
| F4 limits/errors | maxlength 200, required, empty state, error display, hostile title | tests above | PASS |
| F5 project rules | Templates have no comments/script/URLs; test file has no comments, ruff format and ruff check clean | ruff outputs | PASS |
| F6 check authenticity | Real pytest exit 0, 35 passed, no skips or suppressions | pytest-run.txt | PASS |

### Evidence Challenge
- R21 order: path = items list → template loop → HTML; the only way to be green but broken is a template-side `|sort`; tests feed deliberately unsorted input and assert output equals input order. Real sorting correctness belongs to C3.1 and is not proven here.
- R20: green-but-broken would be hx-confirm on the wrong form or missing on one of several items; tests check every item's delete form and that no other form carries it. The plain no-JS path has no confirm by design (the contract places hx-confirm only for HTMX); no applicable counterexample within the template contract.
- R45: counterexample class "escaped in text but not in the attribute" is covered by the quote break-out test and by a parsed round-trip of the value. `|safe` is absent from the sources.
- End-to-end flow (routes, 303/422/404, HX-Request branching) is deferred to C3.2 and not claimed.

### Acceptance Tests
| File | Test | Verifies |
|---|---|---|
| tests/acceptance/test_stage3_checklist_templates.py | 35 test cases (28 test functions; parametrized over /shopping and /todos) | order, strikethrough, hx-attributes, hx-confirm, POST-only, escaping, empty/error states, inputs, page vs fragment, source cleanliness |

### Test Run
| Command | Exit code | Passed / Failed / Errors |
|---|---|---|
| timeout 150 uv run pytest tests/acceptance/test_stage3_checklist_templates.py -q | 0 | 35 / 0 / 0 |
| uv run ruff format + uv run ruff check on the test file | 0 | clean |

### Failures
None

### Advisory Notes
- The rename input has aria-label and `required`; the add input has no `autofocus` or `autocomplete="off"` (taste only).
- Done items carry class `is-done` on both `<li>` and `<s>`; harmless duplication.

### Open Questions
None
