# Acceptance Curation

Use in Phase 2: what happens to the acceptance tests left by step ②
(`@pytest.mark.acceptance` from the acceptance owner), and how to accept the
curator's decisions.

## Task

Acceptance tests were written to prove that a specific spec item is implemented
correctly. Some of them are one-run temporary insurance; some are valuable
regression protection. The decision is made by the curator
(`workflow-test-curator`) over the release-scope inventory only; the main
agent accepts/returns decisions but does not edit the tests itself.

## Global-value criterion

A test **carries global value** (→ promote to permanent: remove the marker,
bring the name/docstring to the suite style) if it protects something future
changes can break:

- the public contract of a module/endpoint (request/response shape, error
  codes);
- a domain invariant or a status regression (status transitions, artifacts);
- the class of a fixed defect (bug regression);
- an architecture/security rule (import boundaries, authorization).

A test **carries no global value** (→ delete) only when this is proven:

- it checks incidental details of a single item (exact wording, order of
  internal calls, mock call counts for the count's sake);
- it duplicates an already existing permanent test of the same contract —
  a proven duplicate, not a similar-looking one;
- it only proves "the implementer ran the code" (smoke for smoke's sake);
- it is inherently fragile (sleeps, timings, dependence on a single run's
  data) and cannot be rewritten without losing its meaning.

Unique protection is never lost: if two tests overlap but each pins a distinct
risk, both stay. Doubt is interpreted in favor of keeping (promote or keep as
is) and the doubt is recorded with a reason in the curator's report; a
deletion without a proven reason is a return to the curator. Percent-reduction
targets, deletion quotas and coverage thresholds do not exist in this
protocol — a smaller suite is never a goal in itself.

## Inventory and boundaries

1. Inventory: `grep -rl "pytest.mark.acceptance" tests/`, intersected with the
   release scope — only these files go into the curator's task package; an
   empty inventory means the curator is not launched (decision recorded).
2. The curator edits **only** `tests/`: deleting a test/file, removing the
   marker, adjusting the name/docstring of a promoted test. Project source,
   the spec, and configuration are untouchable.
3. A file consisting entirely of tests being deleted is deleted entirely;
   `conftest.py` is not deleted — it is only relieved of acceptance fixtures
   that have become unused.
4. A defect in an acceptance test itself (wrong oracle, broken fixture) goes
   to the test author within their boundaries — it is not a curation decision
   and does not spend the curator's rework counter.

## Accepting the curator's decisions

1. Read `### Result` (`Verdict: curated | blocked`), then the Decisions table
   (every row: promoted | deleted | kept, with a reason; dubious keeps carry
   the doubt reason).
2. Double-check against `git diff -- tests/`:
   - only inventory acceptance tests are changed/deleted;
   - promoted tests no longer carry the marker;
   - project source untouched (any touch — an automatic return).
3. Re-run the affected scope within the command budgets
   (`defaults.budgets.checks.command_seconds`, output to a file, no pipe) —
   GREEN.
4. A disagreement about a specific decision — a return to the same role with
   comments; the shared counter, limit
   `policies.acceptance.rework_returns`.
5. Record in the state file: how many deleted / promoted / kept, the final
   suite counters per layer.

## Phase 2 result

- No uncurated release-scope acceptance tests remain in `tests/` (or their
  presence is explicitly justified in the report).
- Suite GREEN after the curation; decisions recorded in the state file (input
  for the Phase 5 metrics).
