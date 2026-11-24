# I6. Stage Completion

Load this file right before performing I6, after every item of the stage is
accepted. The main agent verifies the stage's definition-of-done obligations as
a whole, runs the mandatory checks, updates statuses, commits, cleans up, and
stops the session.

## Inputs

- The spec with all stage items `[x]`
- Check commands for the stage (the stage-local pytest set plus stage-specific
  validators)
- The stage's mandatory definition-of-done obligations from the spec stage
  block — its promise, DoD, and checks; the object of the stage-level
  verification below

## Checklist

- [ ] Run the stage-local test set — `uv run pytest` with the explicit paths of
  the stage's accumulated acceptance tests and the directly related existing tests
  (never a bare full-suite run during ② — the full suite belongs to `write-tests`
  ③, `SKILL.md` rule 11) — and the additional checks the stage requires — e.g. the
  skill-local `scripts/validate_stage_completion.py {spec_path}` for spec status
  consistency. The run includes the accumulated acceptance suite of all waves:
  acceptance tests stay in `tests/` (marked `acceptance`) until the `write-tests`
  curator decides their fate — never delete or unmark them at this stage. A failed
  check leaves the stage incomplete. Timeout-wrap the command (≤ 150 s; a
  surviving process past 200 s is a hang): limit the whole process tree,
  output to a file, no pipe — the defaults hold even when no tests-config file
  exists, and once the settings layer lands the effective values come from it,
  with the hang limit always above the command limit.
- [ ] Stage reopened by `write-tests` ③: the uncommitted proof-tests of ③ sit in
  the working tree — the stage-local run must be green together with them (a
  still-red proof-test = incomplete fix, stage stays not-`✅`); commit only this
  stage's files explicitly (`commit-helper`), never `git add -A` — the ③ files stay
  uncommitted for the next `write-tests` pass.
- [ ] Verify the stage's mandatory definition-of-done obligations AS A WHOLE —
  your own duty at stage close, never substituted by the accepted items: walk
  the necessary links BETWEEN the stage's items (each item's output feeds the
  next one as the spec promises) and to the end CONSUMER of the stage — the
  path input → result → consumer at stage level, with the stage-local check
  results above as stage-level evidence. A proven violation or a missing proof
  keeps the stage OPEN — not `✅` — even when every item is `[x]`; a BLOCKED
  stage-level finding also blocks `✅`. Fix it by returning the owning item
  (its rework counter continues) or by an explicit user decision — never by
  closing the stage. Record a stage-level verification report with the evidence
  of the corresponding level and its limitations (what is proven at stage
  level and how, what stays unproven and why) with the run's stage artifacts
  per `references/run-artifacts.md`.
- [ ] Update the spec per `references/spec-status-update.md`: stage heading → `✅`
  (only now); the skill's own row in `## Workflow выполнения` → `🔄 (N из M)` while
  other stages remain, `✅` when all stages are done; never other skills' rows.
- [ ] Determine `next_skill` per the remaining stages: unchecked stages remain →
  `implement-spec-stage`; all stages `✅` → `write-tests`.
- [ ] Commit via `commit-helper`; then report: spec path, stage statuses, the
  stage-level verification outcome, remaining stages, `next_skill`.
- [ ] Launch the stage impact reporter per `references/stage-impact-report.md`
  — exactly one stage-level sub-agent, uniform across host policies, launched
  by the main agent once the stage is `✅` and the commit exists, before run
  cleanup and the session stop. The reporter is advisory: a failed or
  unavailable reporter never reopens the closed stage, never blocks the
  commit, the transition, or `next_skill`, and never touches acceptance
  statuses or rework counters — reflect the failure honestly in the chat and
  continue.
- [ ] After the successful commit, clean up the run directory per
  `references/run-artifacts.md` (Cleanup): verify the absolute path is inside
  the current run, delete only that directory. On any earlier failure or a missed
  commit, the run files are kept and the run is not closed.
- [ ] Stop the session (one stage per session); suggest `/clear`.

## Result

The stage is `✅` with passing checks and a recorded stage-level verification,
the commit exists, statuses and the next skill are announced, and only this
run's temporary files are deleted.

## Transition

- The session stops. Next skill: `implement-spec-stage` (new session, next stage)
  or `write-tests` (all stages done).
- Failed checks, a missed commit, or an unproven/violated stage-level
  obligation → the stage stays not-`✅`, run files are kept
  (`references/run-artifacts.md`).
