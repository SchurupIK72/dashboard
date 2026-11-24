# Run Artifacts

Use this reference for everything temporary a workflow run produces: where files
live, how to resume, and what may be deleted. Applies to the workflow skills that
record run artifacts (`plan-release`, `implement-spec-stage`, `write-tests`).

Permanent proof of completion is the accepted spec with its marks, the final files,
the tests, and the commit. Temporary reports serve the work and recovery —
they are never a journal embedded into the spec.

## Layout

```
.ai/workflow-runs/<branch-slug>/<skill>/<stage-or-plan>/<run-id>/
```

- `branch-slug` — spec branch with `/` replaced by `-` (e.g.
  `feature-v1.4.2-user-notifications`)
- `skill` — `plan-release` | `implement-spec-stage` | `write-tests`
- `stage-or-plan` — stage ID (e.g. `stage-1`), plan ID, or `release` for write-tests
- `run-id` — unique per launch of the skill; different runs never overwrite each
  other

Stored per item: the task package, the item baseline (`item_baseline`) and the
item diff (`item_diff`), the sub-agent report (researcher, implementer,
acceptance tester), review remarks, the recorded model choice, and the acceptance
decision (verdict, checked criteria, attempt number — see
`references/task-package.md` for the loop itself). The identities of the
item's implementer and acceptance owner are recorded next to ONE shared rework
counter: one first check plus by default two returns (once the settings layer
lands the number comes from the acceptance policy, never presets); recreating
or resuming an agent and any configured override never reset it. The state
file also records the wave plan (`waves`, `edges`) with the reserved write
scopes, and the item→acceptance-tests mapping used by the wave-close suite
re-run. Each item's report/evidence paths are reserved at package composition
and never shared between parallel items.

Before an item is assigned, the main agent captures its `item_baseline` here: the
status, the diff, and the list of modified and untracked files in the item's area
at that moment — one `base_commit` is insufficient when the working tree is dirty,
because changes accepted from earlier items are uncommitted. At acceptance the
main agent isolates `item_diff`: only the item's own changes, including files the
item created, separated from edits accepted earlier and from foreign ones. Foreign
dirty and untracked files are preserved, never reverted. When the item's changes
cannot be separated from foreign edits, acceptance is blocked — an inseparable
diff is not attributed to the implementer.

The run root holds a short state file: current sub-step/item, accepted items,
links to packages and reports, chosen models, per-item rework counters with the
implementer/acceptor identities (one shared counter per item, never reset by a
relaunch or resume). This is data for the
agent, not a software dispatcher.

The stage impact report of `implement-spec-stage` is a stage-level artifact of
the run: it lives with the stage's run artifacts under the run directory, at
the path named in the reporter's package (e.g. `{run-dir}/impact-report.md` —
see `references/stage-impact-report.md`). Its durable act is the presentation
to the user in the chat; the run-directory copy follows the normal cleanup
rules of this reference, with no separate durable-report obligation.

The chat receives brief summaries only. Raw tool output is stored as a separate file
when needed to substantiate a result; it is never pasted into the chat in full.

## Ownership Registry

Inter-session ownership of a stage (or a fix item) is NOT part of any run
directory: it lives in a per-worktree registry at
`.ai/ownership/registry.json`, managed by `scripts/workflow_ownership.py`
(policy gate `policies.ownership.enabled` from `.ai/workflow.yaml`, resolved by
the shared `scripts/workflow_config.py`).

- One active owner per worktree for a stage-or-fix scope, claimed atomically
  before the changing phase together with the declared write scopes (sources,
  tests, reports). A second claim of the same scope or with intersecting write
  scopes is a `CONFLICT`: it names the owning run and writes no code, tests or
  statuses. Item baselines, item diffs and every report path stay inside the
  scopes the claim reserved.
- Different worktrees and clones are independent: their registries are distinct
  files, and disjoint items inside one owner run in waves
  (`references/parallel-scheduling.md`).
- The claim records the owner identity, the reserved write scopes, the evidence
  paths and the per-item rework counters. On resume the same run gets
  `PRESERVED`: owner, evidence and counters are kept, a counter never
  decreases, and the rework budget continues.
- A claim ends by `release` from the owning run at normal completion (commit
  done). A stale claim is NEVER dropped by age, mtime or PID alone — those
  prove nothing about completion; it is removed only with proven completion or
  an explicit user decision (`break --reason completed|user_decision --proof …`).
- Released claims stay in the registry as history; cleanup of a run directory
  never touches `.ai/ownership/`.

## Resume

When continuing a run, reconcile state with the spec, git, and the actual files
before doing anything:

- Accepted and unchanged items are NOT re-implemented.
- On continuation, re-check each open item's `item_baseline` against the working
  tree: foreign edits that landed in the item's area after the capture invalidate
  the baseline — refresh it before the implementer is launched again.
- Research invalidated by external edits is refreshed before an implementer is
  assigned.
- If a sub-agent is unavailable, relaunch the same role and model with the package
  and the accumulated remarks; the rework counter is not reset.
- An unaccepted item stays open; after the default two rework returns are
  exhausted (the third unsuccessful check) the user decides.

## Successful Completion

For `implement-spec-stage` a run is successfully completed when ONE stage is done,
its checks pass, and the commit succeeds. If the commit did not happen, the run is
not closed — regardless of how green the checks were. At that normal completion the
main agent releases the stage's ownership claim
(`scripts/workflow_ownership.py release --kind stage --scope {stage-id}
--run-id {run-id}`), which frees the write scopes for later waves and runs.
Leftover directories of other runs never block cleanup of the current one.

## Cleanup

Cleanup happens only after successful completion of the current run (the
commit/merge succeeded) and goes through `scripts/workflow_cleanup.py` — a
deterministic file-only tool; no process is ever stopped or killed:

```bash
python scripts/workflow_cleanup.py --branch-slug {branch-slug} --run-id {run-id} \
  [--reference {final-manifest-or-report}]... [--orphans] [--apply]
```

- Default is a dry run: the tool prints a JSON plan (deletions, preservations
  with reasons, evidence relocations) and changes nothing; `--apply` executes
  exactly the enumerated plan.
- Deletion targets are only the current run's own directories under
  `.ai/workflow-runs/{branch-slug}/` (`--run-id`, repeatable), verified to stay
  inside the run tree. A target with an active ownership/resume claim or a
  non-terminal `state.json` (open items, stage not ✅, unreadable state, files
  without a state file) is preserved with the reason named.
- Before deletion every evidence file referenced by the final manifests/reports
  passed via `--reference` is copied to the durable
  `.ai/reports/evidence/<run-tree-path>/...` location and the references are
  rewritten in the referencing document, so surviving manifests keep resolving
  (gated by `policies.cleanup.preserve_referenced_evidence`, default `true`;
  `false` keeps referenced evidence in place instead of relocating it).
  References are matched in forward-slash form (repo-relative or absolute);
  a relocation or reference rewrite that fails keeps the affected run directory
  undeleted so a retry can complete it.
- `--orphans` additionally enumerates leftover run directories as explicit
  deletion candidates: a directory qualifies only when no branch slugs to its
  tree, no spec (active or archived) matches, no active ownership/resume claim
  covers it, and its state proves completion (all recorded items accepted and
  the stage ✅) or it is empty. Any doubt preserves it.
- Both run layouts are recognized: `<branch-slug>/<skill>/<stage-or-plan>/<run-id>`
  and the separate plan-release layout `plan-release/{plan-id}/{run-id}/` (its
  recorded final branch drives the orphan checks). Worktrees are independent:
  the tool sees only the given repository's run tree.
- Never touched in any mode: `.ai/memory-candidates/`, `.ai/specs/draft/`
  (backlog), `.ai/reports/`, the ownership registry `.ai/ownership/registry.json`,
  other branches' run trees, and any foreign, active or ambiguous run.
- A cleanup error is visible (non-zero exit and per-path `failures` in the JSON
  plan) and never hides or undoes an already successful merge. A partial failure
  leaves the affected run directory undeleted and named in the plan.

On failure, rejection, unfinished checks, or a missed commit, all run files are
kept so the work can continue without redoing accepted items.
