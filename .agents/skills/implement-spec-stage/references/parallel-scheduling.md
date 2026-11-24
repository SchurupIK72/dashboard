# Parallel Scheduling

Use this reference in I1 to build the wave plan, and in I2–I5 to execute a wave.
Record order still defines priority, but independent items of one stage run
concurrently in waves.

## Wave Plan

A wave is a maximal set of pairwise-independent OPEN code items of the current
stage. Build waves greedily in record order:

1. Start from the first open item (an item under rework is always first).
2. Add every later open item that is independent of ALL items already in the wave.
3. Close the wave when no further item can be added. The next wave starts again
   from the first remaining open item.

Store the plan in the state file:

```text
waves: [[C1.1, C1.3], [C1.2, C1.4], …]
edges: C1.2 → C1.1 (allowed_files: src/api/__init__.py), …
```

Every edge carries a one-line independence rationale, so a resumed run can rebuild
the plan without re-deriving it.

Reserve every item's write scopes BEFORE any implementer of the wave launches:
its `allowed_files` (sources), its `test_allowed_files` under `tests/`, and its
report/evidence paths under the run directory are recorded with the wave plan
(report paths per item are reserved at package composition). Parallel items of
the wave hold pairwise-disjoint sets in all three dimensions; a reserved path
may be re-reserved by a later wave only after its previous owner is accepted.

The wave's reservations are not just prose in the state file: I1 registers them
mechanically in the inter-session ownership record
(`scripts/workflow_ownership.py reserve`, see `references/i1-entry-selection.md`
and `references/run-artifacts.md`). The overlap rules above — file overlap,
directory-covers-children, aggregation files, test/report intersection, the
conservative undecidable default — are what the script enforces on every
`reserve`; a `CONFLICT` names the owning run and the intersecting paths, and
the second claim writes nothing. Re-reservation of a scope by a later wave
therefore also requires the mechanical step: the previous owner `release`s
after normal completion (or the claim is `break`-released with proven
completion or an explicit user decision) before the new `reserve` succeeds.

## Independence Criteria

Two items are DEPENDENT — never in one wave — when ANY of these holds:

1. **File overlap** — their `allowed_files` intersect; a directory overlaps every
   path inside it. Aggregation and registry files (router aggregation,
   `__init__.py` exports, route/service registries) count as overlap
   for every item that touches them.
2. **Explicit spec dependency** — the spec links the items, or one consumes a
   contract the other introduces (a schema another item's endpoint returns, a
   migration another item's query relies on).
3. **Schema migrations** — two items that both add or edit migration revisions are
   always dependent (revision ordering).
4. **Shared runtime state** — both change the same settings keys, the same
   singleton lifecycle, or startup/shutdown behavior.
5. **Test or report overlap** — their `test_allowed_files` intersect, or their
   reserved report/evidence paths intersect. A shared fixture that both items
   would EDIT (e.g. a `conftest.py` fixture) serializes them: the fixture edit
   of one completes before the other's starts — practically, such items never
   share a wave. Reading an existing shared fixture without editing it does not
   serialize.
6. **Undecidable** — when overlap cannot be decided from the spec and the item
   context, the items are dependent (conservative default).

On claude, non-code items never join waves: the main agent performs them at wave
boundaries, keeping record order. On codex/zcode every checklist item joins a
wave — docs and configuration items are implemented like any other item by their
single implementer; only run bookkeeping stays with the main agent at boundaries.

## Wave Execution

Within a wave, each item follows the same per-item pipeline without waiting for
siblings:

1. claude: researchers of the wave launch in parallel, each with its own fresh
   package. codex/zcode: no researcher — the implementers of the wave launch in
   parallel directly, one per item with its package.
2. claude: only after ALL research reports of the wave are accepted (I2, I3 for
   every item) do the implementers launch in parallel, one per item;
   codex/zcode: the implementers launch once the packages are composed — no
   wave-wide research barrier.
3. When an implementer returns, its acceptance starts immediately (I5) — claude:
   the item's acceptance tester launches; zcode: the item's single independent
   acceptor launches; codex: the main agent accepts personally; acceptance of
   different items runs in parallel.
4. Rework of one item proceeds in parallel with its siblings and never pauses them
   — independence already guarantees no shared edit sites.
5. The wave closes when every item is `[x]` or the run stops.

At wave close, re-run the accumulated acceptance suite of the stage — the explicit
file paths of the stage's own acceptance tests (the state file's item→tests
mapping), never a repo-wide marker sweep or a full-suite run (that belongs to
`write-tests` ③):

```bash
uv run pytest <explicit paths of the stage's acceptance test files> -q
```

Split the set into filename chunks when it exceeds the 150 s budget (`SKILL.md`
rule 11). A failure reopens the owning item (the state file maps every acceptance
test file to its item) with its rework counter continuing. The next DEPENDENT
wave starts only after BOTH hold: every item of this wave is accepted AND the
accumulated stage suite above is green — acceptance alone is not a green light,
and a red suite keeps the dependents waiting while the owner reworks.

## Invariants

- Two implementers NEVER hold overlapping `allowed_files` at the same time —
  and never overlapping `test_allowed_files` or report/evidence paths either:
  parallel items are disjoint in sources, tests, AND reports.
- Every sub-agent receives only its item package; the wave plan lives in the
  state file, never inside a sub-agent context.
- Parallelism is a performance property, never a semantic one: if the environment
  cannot launch sub-agents concurrently, execute the wave sequentially in record
  order — the result must be identical.
- Wave boundaries are the only points where non-code items run and where the next
  wave is planned.

## Wave Failures

- A `blocked` item does not block independent siblings; items that depend on it
  (per the edges) wait or stop together with it.
- An acceptance-suite failure at wave close reopens the owning item only; siblings
  stay accepted.
- When the whole wave is blocked (package contradiction, unavailable model), STOP
  per the applicable reference; run files are kept.
