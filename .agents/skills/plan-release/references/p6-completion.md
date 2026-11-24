# P6. Completion

Load this file right before performing P6. Performed by the main agent.

## Inputs

- Accepted spec from P5

## Checklist

- [ ] Create the branch and save the spec per `references/version-branching.md`.
- [ ] Commit the spec with the commit message from the same reference.
- [ ] Clean up the run directory per `references/run-artifacts.md`: only after
  the successful commit, resolve and verify the absolute path belongs to this
  run, delete only this run directory; a cleanup error is reported to the user,
  never hidden.
- [ ] When release-backlog candidates took part in this run, update
  `.ai/specs/draft/next-release.md` once after the successful commit: absorbed
  entries get the status with date, requirement ID, and spec path; rejected
  entries get the dated reason; unselected entries stay open; no entry is
  deleted or renumbered (Release Candidate Backlog in
  `references/scope-discovery.md`). Without a completed commit the backlog stays
  untouched.
- [ ] Report the result: spec path, branch, commit, and the next step
  `implement-spec-stage`.

## Result

Branch created, spec committed, run files of this launch cleaned up, result
reported to the user.

## Transition

The skill is finished. Next skill: `implement-spec-stage` (start it in a new
session per the one-step-per-session rule). If the commit did not happen, the run
is not complete: keep every run file for resuming without redoing accepted work.
