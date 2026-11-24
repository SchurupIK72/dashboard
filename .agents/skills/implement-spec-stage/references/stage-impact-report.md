# Stage Impact Report

Use this reference in I6, after the stage is `✅` and the commit exists, before
run cleanup and the session stop. The stage impact report gives the user a
readable account of what the closed stage changed. This file is the contract
carrier for the stage impact report; the sections below fix the launch
contract — the trigger, the single-reporter rule, the host-policy launch
mapping, and the advisory failure semantics. The sections after them fix the
reporter's package contract: the isolated task package built on the stage's
item reports, the write rights, and the honest treatment of source gaps. The
closing sections fix the report's visibility contract: the content rules that
keep the report at the level of product meanings and the main agent's
presentation duty in the chat.

## Launch Trigger

- The trigger fires once per stage closing sequence: the stage heading is `✅`,
  every item is `[x]`, the stage-level definition-of-done verification is
  recorded, and the commit exists. Nothing before the commit launches the
  reporter.
- The launch happens after the commit exists and before run cleanup and the
  session stop, so the report reaches the chat of the session that closed the
  stage.
- Only the main agent launches the reporter — never per item, never per wave,
  never by another sub-agent.

## Single Stage-Level Reporter

- Exactly one stage-level reporter sub-agent per run of the closing sequence:
  never one per item, never an extra role of step ② items or of the short-fix
  route F①.
- The reporter is a self-sufficient stage role of step ② and never a
  participant in acceptance: it writes no code, no tests, and no statuses, and
  its output never gates item verdicts, the stage close, or the transition.
- Nested delegation is forbidden: the reporter never launches sub-agents of
  its own, and no item role routes its work through the reporter.

## Host-Policy Launch Mapping

The reporter is one logical stage-level role — `impact_reporter` — the same on
codex, zcode, and claude: no host adds a second reporter, a per-item variant,
or an acceptance duty. The launch itself follows
`references/agent-orchestration.md`: one fresh isolated launch of the
reporter's task package (never the main chat history) through the host's
adapter; no host invents a separate launch channel or its own isolation
semantics. Model and budget wiring belongs to the common settings layer, not
to a host-specific launch rule: the launch resolves the reporter's model and
budget through the shared resolver of that layer and passes them with the
package — the launch instructions never duplicate the values.

## Advisory Status and Failure Semantics

The reporter is advisory. A reporter failure, an unusable report, or an
unavailable reporter model:

- never reopens the closed stage — the `✅` heading and the item marks stay as
  they are;
- never blocks the commit, the transition, or `next_skill`;
- never touches acceptance statuses, verdicts, or rework counters;
- is honestly reflected by the main agent in the chat: the user sees that the
  stage impact report is missing or failed and why — no silent skip, no
  invented substitute report.

Unlike an item role, an unavailable reporter model does not stop the run.
There is no automatic relaunch loop and no fallback model: after one failed
launch the main agent records the failure in the chat and continues with run
cleanup and the session stop.

## Reporter Task Package

The package is composed by the main agent at launch time, like every launch
package of this skill. The reporter receives the package, never the main chat
history; the launch itself follows `references/agent-orchestration.md`. The
package is built on the materials the stage already produced — it never asks
the reporter to re-derive the stage from the code. Required fields:

| Field | Meaning |
|---|---|
| `repo_root`, `branch` | Repository root and the branch the stage ran on |
| `stage_id` | The closed stage the report covers |
| `items` | One entry per item of the stage: the item wording verbatim from the spec checklist plus the requirement IDs the spec links to it |
| per-item report paths | For every item: the assigned implementer report path and the assigned acceptance report path |
| `stage_dod_report` | Path of the stage-level definition-of-done verification report recorded at stage close |
| summary lists | The per-item `changed_files` and `item_diff` lists in summary form |
| check metrics | The check results (commands and outcomes) as recorded in the item reports — taken from the reports, never re-derived |
| `impact_report_path` | The assigned output path of the impact report — the one file the reporter writes |

List-valued fields are always present, with `[]` when empty — an omitted list
counts as a missing required field.

A package without the report paths — an item implementer or acceptance report
path, the stage-level definition-of-done report path, or the assigned
impact-report path — is rejected: the reporter returns
`INSUFFICIENT_CONTEXT: missing {field}` (the convention of
`references/task-package.md`) and the main agent fixes the package instead of
the reporter compensating from code or chat.

## Write Rights

The reporter writes exactly one file: the impact report, at the assigned path
named in its package. No code, no tests, no spec edits, no statuses, no
run-state files — the advisory-role boundaries of the sections above apply to
every byte it produces. The path convention lives in
`references/run-artifacts.md`: the report is stored with the stage's run
artifacts (e.g. `{run-dir}/impact-report.md`), its durable act is the
presentation to the user in the chat, and the run-directory copy follows the
normal run-artifacts cleanup rules, with no separate durable-report
obligation.

## Honest Source Gaps

The report's sources are the stage's existing materials: the item implementer
reports, the acceptance reports, and the stage-level definition-of-done
report. An independent re-analysis of the code is never the report's source —
code may be read only to clarify a component or skill name, never to
establish what the stage changed. A missing or incomplete item report, or a
missing stage-level definition-of-done report, appears in the impact report
as an explicit gap for that item: no invented effects, no backfilled
narrative. Contradictions between source reports are not resolved silently —
they surface as open questions to the user.

## Report Content: Meanings, Not Code

The report operates in product abstractions. For every item of the stage it
carries:

- the meaning of the item as the spec states it — not the item's implementation
  history;
- the effect on capabilities, behavior, processes, and qualities: what
  appeared, what changed, what got faster, what became more reliable or
  simpler;
- the mapping to the requirement IDs the spec links to the item.

Numbers from the item reports — check counts, timings, token budgets — may
support a claim, never replace its meaning: a metric is not a sentence of
understanding, and the report never degenerates into a list of numbers.

The report always contains at least one mermaid diagram (a flow, an
architecture, or a timeline of the stage) and at least one summary table with
the columns item → meaning → result → effect, one row per item of the stage.

Code is never the narrative. Lines of code, file:line references, and commit
hashes are not report content. Component and skill names are the allowed —
and expected — vocabulary of every effect statement.

## Presentation in the Chat

The main agent presents the report to the user in the chat in full: with the
rendered mermaid diagram and the rendered summary table, never as a file
link, never as a truncated excerpt, and never substituted by its own retelling.
The run-directory copy is an artifact; the presentation in the chat is the
durable act that makes the report the user's.

The report's target budget is the effective `budgets.reports.target_tokens` of
the reporter role, resolved through the common settings layer like every other
parameter of the launch. A report over the target is marked as over-budget in
its own header; it is never truncated to fit — the diagram, the table, and the
per-item meanings are mandatory structure, and there is no character ceiling.
