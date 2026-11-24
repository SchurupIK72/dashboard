# I5. Acceptance

Load this file right before performing I5 for an item whose implementer has
returned. The acceptance owner follows the host policy fixed in I1: claude — the
acceptance tester sub-agent writes and runs the tests, and the functional verdict
is its `passed`; zcode — exactly one independent acceptor writes tests and audits,
and its `passed` verdict still requires the main agent's confirmation; codex — no
acceptance sub-agent: the main agent personally writes and runs the acceptance
tests, investigates the diff, and decides. The main agent performs the formal
check on every host. The checkbox is marked only after the acceptance owner's
verdict and the formal check pass.

The acceptance owner also produces the acceptance evidence — the criterion
matrix, the formal gate audit, and the evidence challenge — recorded in the
acceptance report with exactly the nine sections Result, Acceptance Matrix,
Formal Audit, Evidence Challenge, Acceptance Tests, Test Run, Failures, Advisory
Notes, Open Questions (role definition `templates/agents/workflow-acceptance-tester.md`;
on codex you write it yourself). Target budget 3000 tokens: an over-target report
is marked, never truncated; detailed command output goes only to the evidence
paths assigned in the package; no character ceiling applies.

## Inputs

- The diff produced by the current item and the implementer report
- Item requirements, acceptance criteria, boundaries
- Tester package fields (`references/task-package.md`)

## Checklist

- [ ] Start the acceptance immediately after the implementer returns — in
  parallel with the remaining items of the wave — per
  `references/agent-orchestration.md`. claude: launch the acceptance tester
  sub-agent. zcode: launch exactly one independent acceptor. codex: no launch —
  write and run the acceptance tests yourself. The test author writes acceptance
  tests under `tests/` with the `acceptance` marker and never edits source code
  (on codex the main agent writes the tests but still never edits the item's
  implementation).
- [ ] Acceptance mode by deliverable. A code item is proven by independent
  pytest acceptance tests — normal / boundary / error cases as applicable; the
  oracle is never a copy of the implementation's formula, and checks are never
  weakened to obtain a green result. A documents/configuration item is proven
  by reproducible checks WITHOUT pytest — an explicit command or a described
  procedure, the expected outcome stated up front, the evidence recorded
  (command, exit code, observed result) — `passed` is attainable this way,
  under the same matrix, gates, and evidence challenge. Executable code may
  never hide behind the docs/config exception.
- [ ] Verify the acceptance package before any testing
  (`references/task-package.md`, acceptance package): beyond the base fields it
  must carry `stage_definition_of_done`, `item_contribution` with the duties
  explicitly deferred to other items, `implementer_report`, `changed_files`,
  `item_diff`, `test_directives`, `test_allowed_files`, and the assigned
  evidence paths. The acceptance criteria come from the spec — the implementer
  report is never the oracle. A package missing a criterion or the item
  contribution blocks the acceptance until you amend it; the owner never
  invents or drops criteria. A duty explicitly deferred to another item is not
  this item's to prove.
- [ ] Read the acceptance report against its role definition
  (`references/agent-orchestration.md`, Report Check); parse
  `Verdict: passed | failed | blocked` first. On zcode a `passed` acceptor
  verdict is recorded but the item is accepted only after your own confirmation;
  on codex the verdict is yours.
- [ ] Matrix completeness: the Acceptance Matrix section holds a row for EVERY
  mandatory criterion of the item — an independent expected result with its
  source, evidence (test / command / file:line), and a status
  PASS / FAIL / BLOCKED / N/A; every N/A needs a justification of
  inapplicability. A green suite with an unproven mandatory criterion stays
  `blocked`.
- [ ] Formal Audit gates: F1 boundaries, F2 requirements, F3 contract
  compatibility, F4 applicable limits/error handling, F5 project rules, F6 check
  authenticity (real exit codes, no suppressed failures) — every gate carries
  evidence and a status (`references/stage-implementation.md`); points or scores
  never compensate a FAIL or BLOCKED gate, and one such gate rules out `passed`.
- [ ] Evidence Challenge: acceptance checks evidence sufficiency, not only green
  tests — the path input → result → consumer for the criterion, the applicable
  invariants and dependencies from the contract, and a substantive
  counterexample of the class "the check is green but the promise is broken", or
  a justified statement that no applicable counterexample exists. Reading
  dependencies beyond the diff is allowed and never expands write rights.
- [ ] Verdicts: `passed` only with complete proof of all applicable mandatory
  criteria and gates; a PROVEN violation → `failed`; otherwise missing
  mandatory evidence → `blocked`; a combination returns `failed` with the
  blocking list enumerated. Taste-level remarks live in Advisory Notes and never
  block. Apply the same rules to your own confirmation and, on codex, to your
  own verdict.
- [ ] `failed` → return the item to the SAME implementer with the acceptance
  owner's Failures list attached as concrete remarks (back to I4). Rework
  budget: ONE shared counter per item — one first check plus by default TWO
  returns; your own formal-check remarks enter the SAME budget, they are never
  free extra rounds. The default two is the default, not a permanent constant:
  once the settings layer lands, the number comes from the acceptance policy,
  never from presets. Record the implementer's and the acceptance owner's
  identities next to the counter — both stay the same for the whole item. The
  third unsuccessful check stops the run for a user decision: no fourth
  attempt, and recreating or resuming an agent never resets the counter. A
  defect in the test itself is fixed by the test owner (claude: tester; zcode:
  acceptor; codex: you) and re-run within the command budgets — it never
  consumes the implementer counter.
- [ ] An item offering NO reproducible check at all (e.g. a purely visual
  change) → verdict `blocked` with the reason; perform the acceptance reading
  of the diff yourself per `references/stage-implementation.md` and decide;
  record why a reproducible check was impossible — never fake coverage.
- [ ] Perform the formal check yourself per `references/stage-implementation.md`
  (Formal Acceptance Check): files within `allowed_files`, report format complete,
  every diff hunk maps to the item, promised checks have real exit codes, and the
  diff carries no comment-pollution violations (spec refs instead of `D##`
  traceability, narrative descriptions, TODO/FIXME, debug leftovers) — such a diff
  goes back as a rework remark, it is not fixed silently. Accept only the
  `item_diff` isolated against the item's `item_baseline` (files created by the
  item included): pre-existing and foreign edits stay out of it and are
  preserved, never reverted; an inseparable foreign diff blocks acceptance
  instead of being attributed to the implementer.
- [ ] Acceptance owner `passed` (zcode: plus your confirmation) AND formal check
  OK → record the verdict
  (`references/task-package.md`, Acceptance Loop), mark the item `[x]` in the spec
  (the first and only moment), update the state file including the
  item→acceptance-tests mapping.
- [ ] Every pytest command (yours and the wave-close suite) names explicit paths
  or node ids — the item's tests plus directly related existing tests only; a
  bare `uv run pytest`, a repo-wide marker sweep, or any full-suite run never
  happens during ② (`SKILL.md` rule 11; the full suite belongs to `write-tests`
  ③). Commands are timeout-wrapped, output to a file, no pipe:
  `PYTHONIOENCODING=utf-8 timeout 150 uv run pytest <explicit paths> >
  {output file} 2>&1`. Budget: one command ≤ 150 s; a surviving process longer
  than 200 s is a hang (Windows post-test teardown — see
  `write-tests/LEARNINGS.md`): kill the whole process tree, then read the
  results from the file — do not wait longer and do not blame the code. These
  defaults hold even when no tests-config file exists — a missing config never
  cancels or widens the limits; once the settings layer lands the effective
  values come from it, with the hang limit always above the command limit.
- [ ] For a stage reopened by `write-tests` ③ (`references/stage-selection.md`,
  Reopened Stages): the red proof-tests of ③ from the item package are part of the
  acceptance oracle — after the fix they must be green; a legitimate contract
  divergence lets you adapt a ③ test (it lives under `tests/`), recording the
  reason in your report.
- [ ] At wave close (`references/parallel-scheduling.md`, Wave Execution): re-run
  the accumulated stage acceptance suite — the explicit paths of this stage's
  acceptance test files from the state file's item→tests mapping
  (`uv run pytest <stage acceptance files> -q`, filename chunks when the set
  exceeds 150 s); a failure reopens the owning item — its rework counter
  continues.

## Result

The item is accepted and marked `[x]`, or returned for one bounded rework round,
or the run stops with a question to the user.

## Transition

- Open items remain in the current wave → their I4/I5 continue in parallel.
- The wave is done → next wave (back to I2) or, when all stage items are `[x]`,
  proceed to I6 — item acceptance alone never closes the stage: the
  stage-level definition-of-done verification of I6 gates the `✅`.
- Stop conditions (rework limit, model unavailability, blocking gap) → STOP; run
  files are kept (`references/run-artifacts.md`).
