# Task Package

Use this reference when preparing a sub-agent launch and when accepting its result.
Applies to the workflow skills that launch sub-agents (`plan-release`,
`implement-spec-stage`, `write-tests`); this skill launches roles according to the host fixed in I1: claude uses the
researcher/implementer/tester chain, codex only the implementer, zcode the
implementer and one independent acceptor. The short-fix route (`apply-small-fix`)
launches its single fix item through this same contract — see Fix-Route Packages
below.

Role definitions (input/output formats) live in the agent files and are NOT
duplicated here:

- Product source: `templates/agents/*.md` (researcher, implementer, acceptance
  tester, spec reviewer, and the write-tests roles)
- Claude runtime: `.claude/agents/workflow-researcher.md`,
  `workflow-implementer.md`, `workflow-acceptance-tester.md`,
  `workflow-spec-reviewer.md`, `workflow-test-curator.md`,
  `workflow-test-writer.md`, `workflow-ui-scenarist.md`
- Codex runtime: `.codex/agents/workflow_researcher.toml`,
  `workflow_implementer.toml`,
  `workflow_acceptance_tester.toml`, `workflow_spec_reviewer.toml`,
  `workflow_test_curator.toml`, `workflow_test_writer.toml`,
  `workflow_ui_scenarist.toml`
- ZCode: `.zcode/agents/workflow-implementer.md` and
  `.zcode/agents/workflow-acceptance-tester.md` from `templates/zcode/`; other
  task-specific roles carry their contract from `templates/agents/{role}.md`

## Package Contract

A sub-agent never receives the main chat history. Everything it must know is in the
package. Required fields for researcher and implementer packages:

| Field | Meaning |
|---|---|
| `repo_root` | Repository root (absolute path) |
| `branch`, `base_commit` | Current branch and the commit the run started from |
| `spec_path` | Path to the spec document |
| `stage_id` / `checkbox_id` | The single stage and item being worked on |
| `item_text` | Verbatim wording of the checklist item (or research question) |
| `requirements` | Related requirement IDs with their acceptance criteria |
| `architecture_constraints` | Boundaries from the spec and `.ai/DECISIONS.md` |
| `allowed_files` | The only files/directories the item may touch |
| `role`, `assigned_model` / `assigned_effort` | Role and the model chosen for this launch |
| `user_decisions` | Relevant user decisions from the interview (when any) |
| `accepted_materials` | Links to accepted packages/reports this item builds on (when any) |

List fields (`dependencies`, `check_commands`, `report_paths`, `accepted_materials`,
`user_decisions`) are always present, with `[]` when empty — an omitted list counts
as a missing required field.

The implementer package additionally carries the execution fields:

| Field | Meaning |
|---|---|
| `item_baseline` | State of the item's area captured by the main agent before assignment: pre-existing dirty and untracked files with their status and diff — `base_commit` alone is insufficient on a dirty tree; storage per `references/run-artifacts.md` |
| `dependencies` | Items this one waits on, with their status — `[]` when none |
| `check_commands` | Commands with which the item verifies its work, with the expected outcome — `[]` when the item defines none |
| `time_budget` | Per-command limit: one command ≤ 150 s (`timeout 150`, output to a file, no pipe, the whole process tree limited); a surviving process past 200 s is a hang — kill the tree, keep the log. The defaults hold even when no tests-config file exists; once the settings layer lands the effective values come from it, with the hang limit always above the command limit |
| `report_paths` | Paths under the run directory for the item's report and its detailed command outputs |

`research_report` is claude-only: on claude the implementer package additionally
contains the accepted output of the researcher for this exact item; on codex/zcode
never — the implementer researches itself, so no researcher report exists to pass.

The command budget is also fixed in the role definitions themselves — a package
missing `time_budget` does not cancel the limit.

The acceptance-tester package additionally contains (plus `time_budget` from the
execution fields above):

| Field | Meaning |
|---|---|
| `stage_definition_of_done` | The stage's definition of done from the spec — the acceptance checks this item's share of it, not the whole stage |
| `item_contribution` | What this item owes toward it, with duties explicitly deferred to other items — a deferred duty is not this item's to prove |
| `implementer_report` | The accepted implementer output for this item — input, never the oracle |
| `changed_files` | Files the implementer created or modified |
| `item_diff` | The item's own changes isolated against its `item_baseline` — the only diff the acceptance judges |
| `test_directives` | Suite run command, known ignores, acceptance marker name |
| `test_allowed_files` | The only files under `tests/` the test author may create or modify — reserved for the item at wave planning, before implementers launch; parallel items hold disjoint sets |
| `evidence_paths` | Paths under the run directory assigned to this acceptance: its report and detailed command outputs — reserved at package composition, disjoint among parallel items |

The acceptance criteria come from the spec — the `requirements`,
`stage_definition_of_done`, and `item_contribution` fields are the oracle; the
implementer report is never the oracle. A package missing a criterion or the item
contribution is blocked: the role reports what is missing, the main agent amends
the package, and criteria are never invented, dropped, or taken from the
implementer's claims.

The write-tests roles use their own packages described in the `write-tests` skill.

The spec-reviewer package replaces stage fields with: `spec_path`, `standard`
(active validation standard + threshold), `project_context` (architecture and
decision documents), `review_scope`.

A missing required field — any field of the tables above, including the implementer
execution fields (`item_baseline`, `dependencies`, `check_commands`, `time_budget`,
`report_paths`) and a list field present only implicitly — must produce
`INSUFFICIENT_CONTEXT: missing {field}` from the role — fix the package instead of
answering the question yourself.

## Fix-Route Packages

The short-fix route (`apply-small-fix`, branch `fix/*`) launches its single item
through the same package contract. Every field above applies unchanged —
`repo_root`, `branch`, `base_commit`, the implementer execution fields
(`item_baseline`, `dependencies`, `check_commands`, `time_budget`,
`report_paths`), and the always-present list fields with `[]` when empty. Only
the source-of-truth fields change:

| Spec item | Fix item |
|---|---|
| `spec_path` | `fix_path` — `.ai/fixes/<slug>.md`, the short statement (symptom / expected / scope / verification). `apply-small-fix` writes the statement before the item launches; the implementer reads it and never creates or edits it. Nothing is created under `.ai/specs` |
| `stage_id` + `checkbox_id` | one item per fix: `fix-1` |
| `item_text` from the stage checklist | `item_text` from the short statement's expected result |
| criteria oracle = the spec | criteria oracle = the short statement at `fix_path` |

A fix item keeps the same role, model, and report rules: the implementer report
carries its seven sections with `Item: fix-1`, the acceptance report carries its
nine sections, and both stay inside the same token budget with details in
`report_paths`. `research_report` stays claude-only — codex/zcode fix items
never receive one, the implementer researches the defect itself; when a fix runs
under the claude policy, the existing researcher → implementer → tester chain
keeps its topology. The acceptance package keeps its extended fields with
`item_diff` isolated against `item_baseline`; `stage_definition_of_done` and
`item_contribution` collapse into the single item's expected result, and the
criteria come from the short statement, never from the implementer's claims.

The acceptance loop is identical: one first check plus at most
`policies.acceptance.rework_returns` returns to the same implementer, one
shared counter, implementer and acceptor identities recorded, no reset on
relaunch. A missing required field — including `fix_path` — produces
`INSUFFICIENT_CONTEXT: missing {field}`. The implementer never commits: the fix
commit is made only after the item is accepted.

## Reports

Report formats are fixed in the role definitions. The `### Result` block is the
machine-readable contract: the main agent parses `Item`/`Release` and `Verdict`
first, then verifies the remaining sections. The main agent:

1. reads the report against the item's acceptance criteria — a claim of success is
   not acceptance;
2. verifies referenced files and checks by reading the diff and re-running what is
   cheap and decisive;
3. stores the report under the run directory (see `references/run-artifacts.md`)
   and keeps the chat to a brief summary.

On codex/zcode the implementer report carries seven sections — Result, Research,
Changed Files, Solution Summary, Criteria Mapping, Checks, Open Questions: Research
documents the files, symbols, and contracts the implementer read and located
itself; Checks carries real exit codes. The target budget is 3000 tokens: a report
over the target is marked as such but never truncated to fit — mandatory content
(all seven sections, real check results) is never cut, detailed command output
goes to the files named by `report_paths`, and no character ceiling applies. The
full layout stays fixed in the role definitions.

The acceptance report carries exactly the nine sections — Result, Acceptance
Matrix, Formal Audit, Evidence Challenge, Acceptance Tests, Test Run, Failures,
Advisory Notes, Open Questions. The Acceptance Matrix proves every mandatory
criterion with an independent expected result and source, evidence, and a status;
the Formal Audit walks the gates F1 boundaries, F2 requirements, F3 contract
compatibility, F4 applicable limits/error handling, F5 project rules, F6 check
authenticity, each with evidence and a status; the Evidence Challenge checks
evidence sufficiency — the path input → result → consumer and a substantive
counterexample of the class "the check is green but the promise is broken", or a
justified statement that none applies (`references/stage-implementation.md`,
Acceptance Evidence Standard). The same budget applies: target 3000 tokens,
over-target marked but never truncated, mandatory content never cut, detailed
command output only in the assigned evidence paths, and no character ceiling
applies.

## Acceptance Loop

A code item is accepted by TWO checks: the functional verdict of the
acceptance-tester suite and the formal check by the main agent. Per item the
implementer's and the acceptance owner's identities are recorded with ONE
shared rework counter. There is one first check and, by default, at most two
returns to the same implementer — the main agent's formal-check remarks enter
the SAME budget. The default two is stated as the default, not a permanent
constant: once the settings layer lands, the number of returns comes from the
acceptance policy (`policies.acceptance.rework_returns`), never from presets.

| Attempt | Actor | Action |
|---|---|---|
| 1 | Acceptance tester | Writes and runs acceptance tests; verdict `passed \| failed \| blocked` |
| 1 | Main agent | Formal check of the diff (boundaries, format, item mapping) and of the tester report format |
| 2–3 | Same implementer | Reworks the tester's failure list and formal remarks — one shared counter; counter increments |
| After 3rd failed check | Main agent | Stops and asks the user; no 4th attempt, no automatic model change, no self-fix of code by the main agent |

Verdict record per attempt: `accepted | rework | blocked`, checked criteria,
concrete remarks, attempt number.

- `accepted` — tester `passed` AND formal check OK; only then the checkbox may be
  marked.
- `rework` — remarks must be specific enough to act on without guessing; a failed
  acceptance suite returns to the implementer with the tester's Failures list.
- A defect in the acceptance test itself (wrong oracle, broken fixture) is fixed by
  the tester and re-run within the command budgets — it does NOT consume the
  implementer counter.
- Relaunching a dead sub-agent, resuming the run, or any configured override
  never resets the rework counter.
- `blocked` — package contradiction, unavailable model, missing dependency, or
  item not verifiable through any reproducible check; dependent work stops
  until resolved (see `references/model-selection.md`).

If a sub-agent dies mid-run, relaunch the same role and model with the package plus
the accumulated remarks; this does NOT reset the rework counter.

## Native launch settings

Codex packages record `assigned_model: gpt-6.1-sol` and `assigned_effort: low`
for every workflow role, including the planning P2 researcher and release roles.
Use unified `workflow_implementer` for implementation. If the API cannot select
a named profile, explicitly pass this pair and the role instructions; do not
inherit the main session. ZCode native implementer and acceptance packages
record `account:zai-individual-coding-plan/GLM-5.3` and `thoughtLevel: max`.
Unavailable required models or isolation block dependent work without fallback.
Claude retains alias selection by complexity.
