# Task Package

Use this reference when preparing a sub-agent launch and when accepting its result.
Applies to the workflow skills that launch sub-agents (`plan-release`,
`implement-spec-stage`, `write-tests`); this skill itself launches only the
researcher and the spec reviewer.

Role definitions (input/output formats) live in the agent files and are NOT
duplicated here:

- Product source: `templates/agents/*.md` (researcher, implementer,
  spec-reviewer, and the other workflow roles), `templates/codex/*.toml`
  (Codex profiles; currently the implementer), `templates/zcode/*.md`
  (ZCode profiles; currently the implementer)
- Claude runtime: `.claude/agents/workflow-researcher.md`,
  `workflow-implementer.md`, `workflow-spec-reviewer.md`
- Codex runtime: `.codex/agents/workflow_researcher.toml`,
  `workflow_implementer.toml`, `workflow_spec_reviewer.toml` — every launch
  at `gpt-6.1-sol` + `low`
- ZCode: pinned profiles where defined — the implementer runs from
  `templates/zcode/workflow-implementer.md` (model and `thoughtLevel: max`
  fixed in the frontmatter); every other role is dispatched as a
  general-purpose sub-agent with the role contract restated from
  `templates/agents/{role}.md`

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

`research_report` is claude-only: on claude the implementer package additionally
contains the accepted output of the researcher for this exact item; on codex and
zcode it never does — the implementer researches itself, so no researcher report
exists to pass.

The spec-reviewer package replaces stage fields with: `spec_path`, `standard`
(active validation standard + threshold), `project_context` (architecture and
decision documents), `review_scope`.

A missing required field must produce `INSUFFICIENT_CONTEXT: missing {field}` from
the role — fix the package instead of answering the question yourself.

## Reports

Report formats are fixed in the role definitions. The main agent:

1. reads the report against the item's acceptance criteria — a claim of success is
   not acceptance;
2. verifies referenced files and checks by reading the diff and re-running what is
   cheap and decisive;
3. stores the report under the run directory (see `references/run-artifacts.md`)
   and keeps the chat to a brief summary.

## Acceptance Loop

Per result there is one first review and at most two rework returns:

| Attempt | Actor | Action |
|---|---|---|
| 1 | Main agent | Reviews the diff itself against spec and architecture; verdict recorded |
| 2–3 | Same implementer | Reworks concrete written remarks; counter increments |
| After 3rd failed check | Main agent | Stops and asks the user; no 4th attempt, no automatic model change, no self-fix of code by the main agent |

Verdict record per attempt: `accepted | rework | blocked`, checked criteria,
concrete remarks, attempt number.

- `accepted` — all criteria verified; only then the checkbox may be marked.
- `rework` — remarks must be specific enough to act on without guessing.
- `blocked` — package contradiction, unavailable model, or missing dependency;
  dependent work stops until resolved (see `references/model-selection.md`).

If a sub-agent dies mid-run, relaunch the same role and model with the package plus
the accumulated remarks; this does NOT reset the rework counter.
