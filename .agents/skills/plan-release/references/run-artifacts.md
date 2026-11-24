# Run Artifacts

Use this reference for everything temporary a workflow run produces: where files
live, how to resume, and what may be deleted. Applies to the workflow skills that
record run artifacts (`plan-release`, `implement-spec-stage`).

Permanent proof of completion is the accepted spec with its marks, the final files,
the tests, and the commit. Temporary reports serve the work and recovery —
they are never a journal embedded into the spec.

## Layout

```
.ai/workflow-runs/<branch-slug>/<skill>/<stage-or-plan>/<run-id>/
```

- `branch-slug` — spec branch with `/` replaced by `-` (e.g.
  `feature-v1.4.2-user-notifications`)
- `skill` — `plan-release` | `implement-spec-stage`
- `stage-or-plan` — stage ID (e.g. `stage-1`) or plan ID
- `run-id` — unique per launch of the skill; different runs never overwrite each
  other

For `plan-release` the spec branch does not exist while planning: the run lives
under `plan-release/{plan-id}/{run-id}/` directly, where plan-id is a short
kebab-case slug of the request topic fixed when the directory is created (P2).
The directory is never renamed; the final branch name is recorded in the state
file once the spec name is fixed (P4).

Stored per item: the task package, the sub-agent report, review remarks, the
recorded model choice, and the acceptance decision (verdict, checked criteria,
attempt number — see `references/task-package.md` for the loop itself).

The run root holds a short state file: current sub-step/item, accepted items,
links to packages and reports, chosen models, rework counters. This is data for the
agent, not a software dispatcher.

The chat receives brief summaries only. Raw tool output is stored as a separate file
when needed to substantiate a result; it is never pasted into the chat in full.

## Resume

When continuing a run, reconcile state with the spec, git, and the actual files
before doing anything:

- Accepted and unchanged items are NOT re-implemented.
- Research invalidated by external edits is refreshed before an implementer is
  assigned.
- If a sub-agent is unavailable, relaunch the same role and model with the package
  and the accumulated remarks; the rework counter is not reset.
- An unaccepted item stays open; after two exhausted rework returns the user decides.

## Successful Completion

For `implement-spec-stage` a run is successfully completed when ONE stage is done,
its checks pass, and the commit succeeds. If the commit did not happen, the run is
not closed — regardless of how green the checks were. Leftover directories of other
runs never block cleanup of the current one.

## Cleanup

Cleanup happens only after successful completion of the current run:

1. Resolve the absolute path of the current run directory and verify it is inside
   `.ai/workflow-runs/` AND belongs to this run-id.
2. Delete only that directory. Files of other runs, specs, and final artifacts are
   never touched.
3. A cleanup error is reported to the user and never hidden; a partial failure
   leaves the run marked as not cleaned.

On failure, rejection, unfinished checks, or a missed commit, all run files are
kept so the work can continue without redoing accepted items.
