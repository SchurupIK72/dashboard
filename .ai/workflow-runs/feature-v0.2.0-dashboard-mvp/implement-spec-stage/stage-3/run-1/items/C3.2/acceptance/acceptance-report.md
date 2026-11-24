# Acceptance report C3.2

Verdict: passed. Tests: tests/acceptance/test_stage3_checklist_routes.py (131 tests, all @pytest.mark.acceptance).
Runs (output files in this directory):
- timeout 150 uv run pytest tests/acceptance/test_stage3_checklist_routes.py -q -> exit 0, 131 passed (pytest-routes-run1.txt, pytest-routes-run2.txt)
- regression test_stage2_protection + test_stage2_login + test_stage1_app -> exit 0, 77 passed (pytest-regression.txt)
- ruff format --check and ruff check on the test file -> exit 0 (ruff-format.txt, ruff-check.txt)
Earlier first run had one failure of my own test (equal done_at timestamps on Windows clock tick between two quick toggles; tie-break id DESC is correct per contract); fixed with time.sleep(0.05) between toggles, then 2 consecutive green runs.
Criteria R17-R22, R45, R48, R14 and the router response matrix are all PASS; see the final message for the full matrix.
