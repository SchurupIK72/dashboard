# Subagent Pipeline — write-tests

Use before launching this skill's sub-agents (curator, test writer, scenarist)
and when accepting their reports. Roles receive a task package, never the main
chat history. Role definitions (input/output formats) live in the agent files
and are not duplicated here:

- Product source: `templates/agents/workflow-test-curator.md`,
  `workflow-test-writer.md`, `workflow-ui-scenarist.md`
- Claude runtime: `.claude/agents/workflow-test-curator.md`,
  `workflow-test-writer.md`, `workflow-ui-scenarist.md`
- Codex runtime: `.codex/agents/workflow_test_curator.toml`,
  `workflow_test_writer.toml`, `workflow_ui_scenarist.toml`
- ZCode: `.zcode/agents/workflow-test-curator.md`,
  `workflow-test-writer.md`, `workflow-ui-scenarist.md` (static host
  templates in `templates/zcode/`, models pinned per host)

## Roles and models

| Role | Purpose | Model slot |
|---|---|---|
| `workflow-test-curator` | curates the release-scope acceptance inventory: deletes only proven duplicates and one-off execution-detail checks, promotes the rest | `defaults.models.{host}.test_curator` |
| `workflow-test-writer` | writes the permanent tests from the test targets | `defaults.models.{host}.test_writer` |
| `workflow-ui-scenarist` | writes the UI scenario for the main agent to execute | `defaults.models.{host}.ui_scenarist` |

The host (`codex | zcode | claude`) is the session host; the model is taken
from the slot, never chosen ad hoc. Model or isolation unavailability is a
blocking stop without silent substitution. A role never launches sub-agents of
its own, and roles of step ③ never join the items of ②/F①.

## Task packages

Mandatory fields for all roles: `repo_root`, `branch`, `spec_path`,
`time_budget` (one command within `defaults.budgets.checks.command_seconds`,
timeout-wrapped, output to a file, no pipe; a process past
`defaults.budgets.checks.hang_seconds` is a hang — kill the tree, keep the
log), `report_paths` (paths under the run directory for the role's report and
detailed command outputs).

| Role | Additional mandatory fields |
|---|---|
| Curator | `release_scope` (stages/items of this release), `acceptance_marker`, `curation_criteria` |
| Test writer | `release_scope`, `test_targets` (module → layer), `pattern_references`, `coverage_expectations`, `slow_marker` (name of the slow-tier set of the project) |
| Scenarist | `ui_scope` (user scenarios and criteria from the spec), `changed_ui_files`, `scenario_output_path`, `environment_hints` |

List fields are always present, `[]` when empty. A missing mandatory field →
the role answers `INSUFFICIENT_CONTEXT: missing {field}`; fix the package, do
not answer for the role.

## Reports: defects and architecture notes

- The `Implementation Defects` section of the test writer's report — suspected
  implementation defects (the test matches the spec, the code diverges): red
  test + spec item + divergence location. The writer does not mask red
  (skip/xfail/weakened assert) and does not stop working on the remaining
  targets. Diagnosis and the registry are handled by the main agent
  (`references/defect-handling.md`).
- The `Architecture Notes` section of the curator's and test writer's reports —
  new fixtures/patterns/layers/markers that appeared in the suite: input for
  updating the sections of `.ai/TESTS_ARCHITECTURE.md` (Phase 5).

## Order and parallelism

1. The curator is launched first (temporary tests are curated before permanent
   ones are written). An empty release-scope inventory → no curator; the
   decision is recorded in the state file.
2. The scenarist (if UI verification is decided) may run in parallel with the
   curator: the scenario depends only on the spec and the diff, and its single
   output file does not intersect `tests/`.
3. The test writer is launched only after the curator's acceptance and the
   tracing (Phase 3): permanent tests are written on top of the already
   curated suite.
4. Between launches the main agent performs tracing and metrics itself — no
   idle time is needed.

## Accepting reports

Report formats are pinned down in the role files; the target budget is
`defaults.budgets.reports.target_tokens` tokens (an over-target report is
marked as such, never truncated; detailed command output goes to
`report_paths`). `### Result` is the machine-readable contract: `Release` and
`Verdict` (`curated | written | scenario_ready | blocked`) are parsed first,
then the other sections are checked (completeness, absence of placeholders,
declared files/commands matching reality). The main agent:

1. re-reads `git diff -- tests/` (or the run-artifacts directory for the
   scenarist) — a claim of success is not acceptance;
2. re-runs the cheap and decisive checks within the command budgets;
3. saves the report to the run directory; in the chat — only a brief summary.

Rework cycle: the first review plus at most `policies.acceptance.rework_returns`
returns to the same role with specific remarks; the counter is shared per role
result, and relaunching a role or resuming the run never resets it; after the
budget is exhausted — STOP and a question to the user. Test defects of the
roles' own making (wrong oracle, broken fixture) are fixed by the test author
without spending the rework counter. The main agent neither writes nor edits
tests itself.

## Run artifacts

`.ai/workflow-runs/{branch-slug}/write-tests/release/{run-id}/`: the state
file (UI decision, links to packages/reports), role packages and reports, the
UI scenario, evidence files, the evidence manifest and defect registry. The
directory is deleted only after a successful Phase 7 commit; on failure or a
batch reopen — it is preserved. Full cleanup of the branch directory is the
`integrate-release` step.
