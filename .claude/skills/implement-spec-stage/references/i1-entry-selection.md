# I1. Entry And Stage Selection

Load this file right before performing I1. The main agent validates entry, selects
the one stage for this session, orders its items, and creates the run directory.

## Inputs

- Current git branch and repository state
- `.ai/specs/{branch-name}.md`
- Repo-root `scripts/validate_workflow_state.py`

## Checklist

- [ ] Read `LEARNINGS.md`; apply only lessons relevant to the selected stage.
- [ ] Run `python {repo_root}/scripts/validate_workflow_state.py --step implement-spec-stage`
  (path from the repository root, not from the skill directory). Exit code ≠ 0 →
  print issues/warnings and STOP.
- [ ] Confirm the spec exists at `.ai/specs/{branch-name}.md`.
- [ ] Select exactly one stage per `references/stage-selection.md` (first 🔄, else
  first ⬜ whose dependencies are all ✅).
- [ ] List the stage items in record order; classify each as code or non-code
  (`references/stage-selection.md`, Code vs Non-Code).
- [ ] Determine the host policy for the whole run and record it in the state
  file (the `host_runtime` field already used in practice): codex | zcode |
  claude. Determine the host from the session environment — which runtime layer
  loaded this skill: `.claude/skills/` → claude; `.agents/skills/` under the
  Codex CLI → codex; `.agents/skills/` under ZCode → zcode. The policy is fixed
  before any item assignment and gates every later sub-step: codex — one
  self-sufficient implementer per item, acceptance personally by the main
  agent; zcode — implementer plus exactly one independent acceptor, the
  verdict confirmed by the main agent; claude — researcher → implementer →
  acceptance tester. The host cannot be determined or is ambiguous → STOP and
  ask the user; a silent fallback to any policy is forbidden.
- [ ] Build the wave plan per `references/parallel-scheduling.md`: dependency
  graph over the code items (allowed_files overlap, spec dependencies, migrations,
  shared runtime state), waves of pairwise-independent items, one-line rationale
  per edge. Store `waves` and `edges` in the state file.
- [ ] Reserve inter-session ownership of the stage BEFORE any implementer of the
  changing phase launches — one atomic claim per worktree for
  worktree/branch/stage plus the declared write scopes of every planned item
  (its `allowed_files`, its reserved `test_allowed_files` under `tests/`, and
  its report/evidence paths under the run directory):

  ```bash
  python {repo_root}/scripts/workflow_ownership.py reserve \
    --repo {repo_root} --kind stage --scope {stage-id} --branch {branch} \
    --run-id {run-id} --owner {main-agent-session} \
    --sources <item allowed_files…> --tests <item test_allowed_files…> \
    --reports <item report/evidence paths…>
  ```

  The policy gate is `policies.ownership.enabled` in `.ai/workflow.yaml`
  (resolved by the shared `scripts/workflow_config.py`; the script reads it,
  no second source of parameters). `RESERVED` → proceed. `CONFLICT` (exit 1)
  → print the reported owner/run and the intersecting scopes, write NO code,
  tests or spec statuses, and STOP for the user; exactly one owner exists.
  Registry lives at `.ai/ownership/registry.json` inside this worktree, so a
  different worktree or clone never conflicts.
- [ ] Create the run directory
  `.ai/workflow-runs/{branch-slug}/implement-spec-stage/{stage-id}/{run-id}/` and
  store a short state file at its root: current sub-step/wave, accepted items,
  links to packages and reports, chosen models, rework counters, item→acceptance-tests
  mapping (`references/run-artifacts.md`).
- [ ] When resuming an interrupted run: reconcile the state file with the spec,
  git, and the actual files; accepted unchanged items are not re-implemented;
  research invalidated by external edits is refreshed; rebuild the wave plan from
  the recorded edges (`references/run-artifacts.md`, Resume). Then run
  `scripts/workflow_ownership.py resume --kind stage --scope {stage-id}
  --run-id {run-id}` — same run: `PRESERVED` keeps the owner, the evidence list
  and the rework counters (a counter never decreases); another run: `CONFLICT`
  names the owner and nothing is written. A stale claim is NOT dropped by age,
  mtime or PID: it ends only via the owner's `release` after the normal
  completion, or via `break --reason completed|user_decision --proof …` with
  proven completion or an explicit user decision.
- [ ] When the stage was reopened by `write-tests` ③ (`references/stage-selection.md`,
  Reopened Stages): read the defect-registry link near the stage heading, take the
  uncommitted red proof-tests of ③ into the item packages as the oracle, and keep
  those files out of this run's commits (stage files explicitly).

## Result

One selected stage with dependencies complete; the host policy recorded in the
state file; an ordered item list with code/non-code classification; a wave plan
with dependency rationale; an active ownership reservation covering the declared
write scopes of the wave; a run directory with a state file.

## Transition

- Proceed to I2 for the first wave (or the item under rework).
- All items of the stage are already `[x]` → proceed to I6.
- No admissible stage, failed entry validation, or ambiguous stage → STOP and tell
  the user.
