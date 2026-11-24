# Defect Handling — write-tests

Use when permanent tests (Phase 4), tracing (Phase 3), or the UI scenario
(Phase 6) discover a discrepancy between the implementation and the spec.
Protocol: testing runs to the end and collects **all** defects; then all
affected stages are reopened **in a batch**, not one at a time.

## Principle

Step ③ is the only full review of the implementation after ②. Stopping at the
first defect means hiding the rest. Protocol: diagnosis → collecting the full
registry → batch reopen → STOP of step ③ without a commit. Point edits to the
implementation at step ③ are forbidden — a defect is closed only by the full
mechanics of ② through its own roles (the reopened-route roles of the host
policy; a separate researcher for the reopened route is not restored).

## Diagnosis: wrong test or wrong implementation

A red test is not automatically an implementation defect. The main agent
(without editing code or tests) cross-checks the test ↔ spec item ↔ code:

| Verdict | Signs | Action |
|---|---|---|
| Wrong test | oracle/fixture error; the test contradicts a spec item | a rework return to the same test author with comments (the shared counter, limit `policies.acceptance.rework_returns`) — does not spend the implementer-side budget of ② |
| Confirmed defect | the test matches the spec; the code diverges from the spec item | an entry into the defect registry; testing continues |
| Unclear | insufficient context after reading the code and the spec | a clarifying run/read; if still unclear — a question to the user in the final report |
| Dependent unreachable | the check cannot run because of an earlier confirmed defect (e.g., a UI step behind a broken flow) | marked blocked with the reference to the blocking defect; not counted as its own defect |

The input to diagnosis is the sub-agents' reports: the test writer reports
suspected defects in the `Implementation Defects` section instead of masking
them; the UI executor records every unexpected step with evidence. Masking a
red test (skip, xfail without a user decision, weakening an assert) is
forbidden and is itself a return to the author.

## Collecting all defects

The first confirmed defect does NOT stop step ③:

1. The test writer keeps writing tests for all remaining test targets; the red
   evidencing tests stay in `tests/` as is.
2. The UI scenario (Phase 6) is executed to the end: every unexpected step is
   recorded as a defect with evidence, state is restored, the scenario
   continues (`references/ui-verification.md`); steps unreachable because of
   an earlier defect are marked blocked.
3. The curator's decisions (Phase 2) are not rolled back: acceptance-test
   curation does not depend on implementation defects.
4. Metrics (Phase 5) are measured as usual, but the history row in
   `.ai/TESTS_ARCHITECTURE.md` is not written — history is kept for completed
   runs; the numbers stay in the run-directory report.

## Batch reopen (end of step ③)

When all test targets are covered and the UI scenario (if any) has been run to
the end:

1. Compose the defect registry `defect-report.md` in the run directory:
   stage → item → criterion → defect → evidencing test (file/test) → run
   evidence (output or screenshot), plus the blocked dependent checks with
   their blocking-defect references.
2. Update the spec in one pass:
   - every affected stage `✅` → `🔄`; affected items `[x]` → `[ ]`;
   - the `implement-spec-stage` skill row in `## Workflow выполнения` returns
     to `🔄` — the single exception to "each skill edits only its own row":
     this is the outcome of step ③'s acceptance, recorded together with the
     defect report;
   - the `write-tests` own row stays `⬜` — the step is not completed;
   - one reference line to the defect registry next to the headings of the
     reopened stages.
3. Step ③ tests are NOT committed: green and red ones remain in the working
   tree (commits stage files explicitly — ② commits must not pick them up);
   the defect registry is in the run directory, which is preserved when the
   step is incomplete.
4. STOP of step ③: the final report to the user — the full defect registry,
   affected stages, blocked dependent checks, test state;
   `next_skill: implement-spec-stage`.

## Return to implement-spec-stage

Reopened stages are closed by the full mechanics of ② (research →
implementation → acceptance per the host policy, through sub-agents and their
artifacts):

- the ③ red evidencing tests (proof-tests) go into the reopened item's task
  package as the oracle: after the fix they must turn green;
- if the fixed contract legitimately diverges from a ③ test, the acceptance
  tester adapts the test (the file lives under `tests/` — within their
  boundaries) and records the reason in the report;
- choosing a stage with several `🔄` — per the rules of
  `implement-spec-stage/references/stage-selection.md` (order by
  dependencies; a question to the user — only on genuine ambiguity);
- the rework counter of the old, interrupted work is never reset: relaunching
  a role, resuming the run or any configured override keeps the count;
- the next `write-tests` pass after the stages are closed starts from Phase 1
  anew: the interrupted run did not end with a commit; curation and writing
  proceed from the current suite state.
