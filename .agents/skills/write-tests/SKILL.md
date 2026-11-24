---
name: write-tests
description: >
  Workflow step ③: sub-agent testing system for implemented code.
  Triggers: "write tests", "напиши тесты", "create tests", "создай тесты",
  "cover with tests", "покрой тестами", "test-writer", "write a check",
  "напиши проверку".
  The curator curates the temporary acceptance tests left by step ②, the
  test-writer sub-agent writes the permanent tests, the scenarist prepares
  the UI scenario, and the main agent accepts the reports, keeps the metrics
  and — by its own Phase 1 decision — executes the UI scenario with the
  browser tools of its session. Implementation defects are collected to the
  end and the affected stages are batch-reopened (defect handling); models
  and budgets come from .ai/workflow.yaml.
type: workflow
step: 3
---

# Write Tests

**Workflow step ③** — sub-agent testing system: acceptance-test curation, permanent tests, metrics, optional UI verification, batch reopen on implementation defects.

## Workflow Contract

```yaml
entry:
  branch: NOT main | master
  artifacts:
    - .ai/specs/{branch-name}.md
  condition: all stages in the spec have status ✅

exit:
  condition: acceptance tests curated, permanent tests written, evidence manifest completed (run_status: completed), metrics history row recorded
  alt_exit:
    condition: confirmed implementation defects found (defect handling) — every test target checked to the end, defect registry collected
    action: batch reopen of the affected stages in the spec (stage `🔄`, items `[ ]`, defect-registry link near the reopened headings); step ③ tests and defect evidence stay in the working tree without a commit
    next_skill: implement-spec-stage
  artifacts:
    - tests/**/*.py
    - .ai/TESTS_ARCHITECTURE.md  # metrics history row, completed runs only

next_skill: integrate-release

uses:
  - commit-helper
  - playwright-testing  # only for executing the UI scenario (Phase 6), per the Phase 1 decision
```

## Repo-root Artifacts

| Artifact | When to read | Purpose |
|---|---|---|
| `.ai/workflow.yaml` | Phase 1, then as needed | The only parameter source: budgets (`defaults.budgets.checks.*`, `defaults.budgets.testing.*`, `defaults.budgets.reports.target_tokens`), the rework policy (`policies.acceptance.rework_returns`), role model slots (`defaults.models.{host}.test_curator/test_writer/ui_scenarist`). The skill never edits it |
| `.ai/TESTS_ARCHITECTURE.md` | Phase 1 and Phase 5 | Test architecture of the target project (installed from `templates/TESTS_ARCHITECTURE.md.tpl`): layers, fixtures, conventions, metrics history |
| `scripts/validate_workflow_state.py` | In the ENTRY check (Phase 1) | Shared workflow state gate (`--step write-tests`). Path is **from the repository root**, not from the skill directory |
| `scripts/test_evidence.py` + `schemas/test-evidence.json` | Phases 5 and 7 | Test evidence engine: explicit selection, chunk planning, reconciliation, schema-validated manifests. Field and flag names are defined there and are not re-described here |

## Skill-local Supporting Files

| File | When to read |
|---|---|
| `references/subagent-pipeline.md` | Before launching sub-agents (Phases 2, 4, 6) and when accepting their reports |
| `references/acceptance-curation.md` | In Phase 2, before curation and when accepting the curator's decisions |
| `references/defect-handling.md` | On the first red test / discrepancy with the spec (Phases 3, 4, 6) and before the batch reopen |
| `references/context-gathering.md` | Before tracing changed modules (Phase 3) |
| `references/test-layer-selection.md` | When choosing `unit` / `api` / `integration` / `architecture` (Phase 3) |
| `references/coverage-matrix.md` | Before writing tests (task package for the writer) and when checking completeness |
| `references/test-patterns.md` | Before composing the task package for the test writer |
| `references/test-metrics.md` | In Phase 5: measurement, soft thresholds, history recording |
| `references/ui-verification.md` | In Phase 1 (decision) and Phase 6 (scenarist + execution) |
| `references/sufficiency-gate.md` | Before running the final check and committing |
| `scripts/collect_test_targets.py` | Optional: build the test targets table from spec + diff |
| `scripts/validate_test_completion.py` | Optional: verify that the new tests cover the changes |

## Division of Labor

- **Curator** (`workflow-test-curator`) — the only role that deletes or promotes acceptance tests; edits only `tests/`.
- **Test writer** (`workflow-test-writer`) — writes the permanent tests; edits only `tests/`, deletes nothing.
- **Scenarist** (`workflow-ui-scenarist`) — writes the UI scenario; edits exactly one file in the run directory.
- **Main agent** — tracing, task packages, acceptance of reports, metrics, executing the UI scenario in the browser, git; never writes tests itself.

Roles of step ③ never join the items of ②/F①, never receive the main chat history, and never launch sub-agents of their own.

## Algorithm

### Phase 1: ENTRY check and decisions

1. Run `python {repo_root}/scripts/validate_workflow_state.py --step write-tests` (path from the repository root); if the exit code ≠ 0 — print issues/warnings and STOP.
2. Check the branch: `git branch --show-current`; find the spec `.ai/specs/{branch-name}.md`; make sure all stages are `✅`.
3. Create the run directory `.ai/workflow-runs/{branch-slug}/write-tests/release/{run-id}/` with a state file (decisions, links to packages/reports).
4. Make the UI verification decision per `references/ui-verification.md` (criteria: changes in templates/pages/static/js or web routes with HTML responses of the target project, user scenarios in the spec phrased as visible behavior). Record the decision (yes/no + rationale) in the state file.
5. Read `.ai/TESTS_ARCHITECTURE.md` (current suite state) and resolve the effective budgets from `.ai/workflow.yaml` (per-command and hang limits, testing targets, report token target, rework policy, role model slots).

### Phase 2: Curator of acceptance tests

1. Collect the release-scope inventory of acceptance tests: `grep -rl "pytest.mark.acceptance" tests/`.
2. Launch the curator with a task package per `references/subagent-pipeline.md` and `references/acceptance-curation.md`. An empty inventory → the curator is not launched; the decision is recorded in the state file.
3. Accept the curator's report: check `git diff -- tests/` — only inventory acceptance tests deleted/promoted, project source untouched; re-run the affected scope budget-wrapped.
4. If necessary — a rework return per `references/subagent-pipeline.md` (the shared counter, limit `policies.acceptance.rework_returns`).

### Phase 3: Tracing

Use `references/context-gathering.md`. Build on step ② artifacts: acceptance tests in `tests/` (what is already proven and by what), item statuses in the spec, stage commits. Read the changed files (spec or `git diff --name-only`): public contract, data flows, file artifacts, config/feature flags. If the list is fuzzy — `scripts/collect_test_targets.py`. Result: a test targets table (module → layer) per `references/test-layer-selection.md`.

A discrepancy between the code and a spec item found during tracing is an entry into `references/defect-handling.md` (defect registry), not a reason to silently adjust the test targets to the code.

### Phase 4: Permanent tests

1. Compose the task package for the test writer: test targets, pattern references (`references/test-patterns.md`), coverage expectations (`references/coverage-matrix.md`), the curator's report, `time_budget` (`references/subagent-pipeline.md`).
2. Launch `workflow-test-writer` per `references/subagent-pipeline.md` — only after the curator's work is accepted; the scenarist (if decided) may run in parallel without write intersections.
3. Accept the report: re-run the new tests budget-wrapped, check completeness against the coverage matrix and `references/sufficiency-gate.md`; if necessary — a rework return (shared counter, limit `policies.acceptance.rework_returns`).
4. A red test with a suspected implementation defect is an entry into `references/defect-handling.md`: diagnose "wrong test vs wrong implementation"; a confirmed defect goes into the registry while testing continues over all remaining targets. Step ③ is not stopped at the first defect; a dependent unreachable check is recorded as blocked.

### Phase 5: Metrics

Per `references/test-metrics.md`. Every measurement command is wrapped in the per-command budget (`defaults.budgets.checks.command_seconds`), writes output to a file, no pipe; a process past the hang limit (`defaults.budgets.checks.hang_seconds`) is a hang — kill the process tree, keep the log. Scope selection, chunks and the executed/expected reconciliation are done by `scripts/test_evidence.py` (subcommands `plan` and `reconcile` over an explicit selection of paths/node ids — never a repository-wide sweep); the manifest is the single source of the history-row numbers. Compare the soft targets (`defaults.budgets.testing.*`) by naming the YAML path, not a number; a threshold exceedance is a warning, a second consecutive exceedance of the same target — a mandatory proposal to the user. The history row in `.ai/TESTS_ARCHITECTURE.md` is written only for a completed run; with a non-empty defect registry the numbers stay in the run-directory report. Update the layer/fixture sections from the sub-agents' Architecture Notes; changes to conventions and thresholds are only a proposal to the user.

### Phase 6: UI verification (per the Phase 1 decision)

1. If decided: launch `workflow-ui-scenarist` (may run in parallel with Phases 2–4), accept the scenario.
2. Execute the scenario personally with the browser tools of your session per the `playwright-testing` skill and `references/ui-verification.md` (stand identity first, isolated test data); save evidence files to the run directory.
3. An unexpected step result is not a STOP but a defect into the registry (`references/defect-handling.md`): record step/expectation/actual + evidence, restore state, continue the scenario to the end. A step unreachable because of an earlier confirmed defect is marked blocked with the reference to that defect. A scenario that cannot be executed (environment, identity, missing browser capability) is blocked with the reason — a fictitious UI PASS is forbidden.

### Phase 7: Run completion and commit

Check completeness per `references/sufficiency-gate.md`; if needed, run `scripts/validate_test_completion.py`. Confirm the manifest of Phase 5 is valid (`scripts/test_evidence.py validate-manifest --manifest {file}`).

**Defect branching:** the defect registry is not empty → the commit path is closed; instead — the batch reopen per `references/defect-handling.md` (spec: stages `🔄`, items `[ ]`, registry link near the reopened headings, `next_skill: implement-spec-stage`, no commit; the ③ proof-tests and the defect evidence stay uncommitted in the working tree).

All sets completed and GREEN → update the `write-tests` skill row in the `## Workflow выполнения` table of the spec file (`⬜` → `✅`); call `commit-helper` (only the files of this step are staged); after a successful commit, clean up this run's directory (`references/subagent-pipeline.md`, run artifacts).

## Rules

- No live API calls in unit tests — use mock/stub; configuration through the project's settings, not hardcoded values.
- Do not invent new patterns if a reference already exists in `tests/`.
- Acceptance tests of step ② are deleted or promoted only by the curator; the main agent and the test writer do not touch them.
- Curation decisions follow `references/acceptance-curation.md`: unique protection is never lost, only proven duplicates and one-off execution-detail checks are deleted, doubt means keep with a reason; percent-reduction targets and coverage thresholds are forbidden.
- Values in `.ai/workflow.yaml` change only by a user decision or an explicit work item; the skill neither raises nor lowers them.
- An implementation defect is not fixed at step ③: collect all of them (`references/defect-handling.md`), batch-reopen the affected stages, `next_skill: implement-spec-stage`; step ③ tests are not committed in this case.
- Every test command is timeout-wrapped per `defaults.budgets.checks.command_seconds`, output to a file, no pipe; a test process past `defaults.budgets.checks.hang_seconds` is a hang, not a slow test — kill the tree, read the results from the file. A test that cannot fit the per-command budget goes to the project's slow tier (a named set), never to silent waiting or a masked red.
- The full-suite scope is an explicit selection of paths/node ids through the evidence engine; a bare repo-wide run, repo-wide marker sweeps and masking a red test with skip/xfail are forbidden.

## Continuous Improvement

After each completed run, perform Improvement Triage:

1. The task was solved without ambiguities → output `no_change`.
2. A reusable lesson was discovered → add a brief entry to `LEARNINGS.md`.
3. The skill instructions led to an error → first create an eval case in `EVALS.md`.
4. Propose a `SKILL.md` patch only if the same problem can recur.
5. Prefer replacing or removing outdated guidance over adding new rules.
6. Do not update `SKILL.md` until the corresponding eval has passed.
