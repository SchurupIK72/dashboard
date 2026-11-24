# Stage Implementation

Use this reference in I4 and I5: what an implementation item may change, who writes
tests, and what the main agent verifies during acceptance.

## Division Of Labor

- An item's implementation (source files, executable scripts; on codex/zcode also
  docs and configuration items) is written by the implementer sub-agent only. The
  implementer NEVER writes tests.
- Acceptance tests are written by the acceptance owner per host policy: claude —
  the `workflow-acceptance-tester` role, which also holds the functional verdict;
  zcode — exactly one independent acceptor whose `passed` verdict the main agent
  confirms; codex — the main agent personally.
- The acceptance owner writes both the tests and the audit: the acceptance
  report carries the criterion matrix, the formal gate audit, and the evidence
  challenge (`references/task-package.md`, acceptance report; the standard is
  defined below in Acceptance Evidence Standard).
- On claude/zcode the main agent never edits code or tests — including fixes
  after review; it returns concrete remarks instead. On codex the main agent
  never edits item source code; it writes and runs the acceptance tests itself
  and returns implementer remarks instead of editing the implementation.
- Run bookkeeping (spec statuses, run reports, running checks, git commands) is
  performed by the main agent directly at wave boundaries on every host; on
  claude, docs and other non-code items are also the main agent's document work
  within an accepted item.

## Boundaries

An item may touch:

- files listed in its `allowed_files`
- small supporting edits required by the architecture

Not allowed without a new checklist item or an explicit user request:

- implementing other items or later stages
- broad refactors
- unrelated cleanup
- changing workflow rules to make implementation easier
- changing public contracts the spec does not explicitly change
- for the implementer: creating, modifying, or deleting anything under `tests/`
  (the acceptance tester's domain)

## Consumer Search Protocol

The implementer while researching and implementing, and the main agent at
acceptance, locate every affected consumer and check — not by file name alone:

- Search by changed symbols (functions, classes, CLI flags, schema fields,
  JSON keys, config literals) and by changed contract literals/selectors
  (marker names, node-ID prefixes, path selectors, regex patterns) across
  source, tests, and harness scripts.
- A rename or literal change ships together with the consumers located this
  way; reading consumers beyond the diff is allowed and never expands write
  rights beyond the item's `allowed_files`.
- The report lists every applicable layer — unit, integration, slow, UI — that
  the change touches, and justifies each exclusion (for example: no UI surface
  exposes the symbol; no slow-marked test references the literal).
- A stub or mock at a component boundary proves only the stubbed side; when a
  contract change crosses the boundary, the stub never substitutes the
  consumer proof required by the acceptance evidence standard (path
  input → result → consumer).
- Incidental interface text — a word in a log line, help string, or comment
  that happens to match a search term — is not a contract; only symbols and
  literals with a real caller or a declared contract count as consumers.

## Working With Dirty Trees

If the worktree has unrelated changes:

- do not revert them
- avoid touching unrelated files
- if a needed file already has user changes, the item works with them carefully
- mention residual risk if verification is limited by unrelated dirty state

The per-item reference points are `item_baseline` and `item_diff`: the implementer
works relative to the baseline captured in its package, and acceptance isolates
the item's own changes — created files included — from pre-existing and foreign
ones per `references/run-artifacts.md`.

## Formal Acceptance Check

During I5 the main agent performs the formal check of the diff (functional
correctness is decided by the acceptance owner per policy). The check runs as six
gates — the same gates the acceptance report's Formal Audit section carries:

1. F1 — boundaries: Are changed files within `allowed_files` (and nothing under
   `tests/` unless the role is the tester)? Does every hunk map to the current
   item and its requirements?
2. F2 — requirements: claude: does the change follow the accepted research
   report? codex/zcode: does the implementer's report document its Research — the files, symbols, and
   contracts it read and located itself — behind the chosen solution? Does the
   Acceptance Matrix prove every mandatory criterion with an independent
   expected result, its evidence, and a status (an N/A justified)?
3. F3 — contract compatibility: Do public contracts stay stable unless the spec
   changes them, and does every affected consumer keep working?
4. F4 — applicable limits and error handling: were the applicable boundary and
   error behaviors exercised, not only the happy path?
5. F5 — project rules: comment cleanliness (traceability via `D##` of
   `.ai/DECISIONS.md` only, no banned marker comments, no debug leftovers) and
   the project rules respected?
6. F6 — check authenticity: Were the promised checks actually run, with real
   exit codes? No failure suppressed, nothing re-run-until-green passed off as a
   check.

Every gate carries evidence and a status; points or scores never compensate a
FAIL or BLOCKED gate. If any answer is unsafe, return the item with concrete
remarks per `references/task-package.md`; do not fix the code yourself.

## Acceptance Evidence Standard

The acceptance owner proves the item; green tests alone do not:

- Criterion matrix — every mandatory criterion of the item gets an independent
  expected result with its source, evidence (test / command / file:line), and a
  status PASS / FAIL / BLOCKED / N/A; an N/A needs a justification of
  inapplicability. A duty explicitly deferred to another item (the item
  contribution recorded in the package) is not this item's to prove.
- Evidence challenge — walk the path input → result → consumer for the
  criterion, check the applicable invariants and dependencies from the contract,
  and give a substantive counterexample of the class "the check is green but the
  promise is broken" — or a justified statement that no applicable
  counterexample exists. Reading dependencies beyond the diff is allowed and
  never expands write rights.
- Verdicts — `passed` only with complete proof of all applicable mandatory
  criteria and gates; a PROVEN violation → `failed`; otherwise missing
  mandatory evidence → `blocked`; a combination returns `failed` with the
  blocking list enumerated. Taste-level remarks are advisory and never block.

The report format carrying this standard is fixed in `references/task-package.md`
and in the role definition `templates/agents/workflow-acceptance-tester.md`.
