# I4. Implementation

Load this file right before performing I4, once every item of the wave has its
recorded model choice and package — on claude after the research reports of the
whole wave are accepted; on codex/zcode directly after package composition. On
every host an item's implementation belongs to the implementer sub-agent only
(codex/zcode: every checklist item, docs and configuration included); on claude a
non-code item is performed by the main agent at a wave boundary.

## Inputs

- Implementer task packages of the wave (claude: with the accepted research
  report; codex/zcode: package contract only)
- Allowed files and item boundaries per item
- The wave plan from the state file (`references/parallel-scheduling.md`)

## Checklist (code item)

- [ ] Launch the implementers of the wave in one parallel batch per
  `references/agent-orchestration.md` — the sub-agent type/role and the model
  follow the adapter mapping there and the recorded choice.
- [ ] Each implementer works only within its `allowed_files`, implements only its
  item, writes NO tests (tests belong to the acceptance owner per host policy),
  and does not commit, update the spec, or mark checkboxes — the main agent owns
  acceptance and status. The implementer works relative to the package's
  `item_baseline`: pre-existing dirty/untracked changes in the item's area are
  preserved, never reverted or absorbed into the item's diff. When a file outside
  `allowed_files` turns out to be needed, the implementer reports `blocked` and
  dependent work stops until the main agent amends the package — boundaries are
  never expanded silently; a requirement change beyond the agreed scope goes to
  the user.
- [ ] The implementer is self-sufficient and launches no sub-agents of its own:
  no nested delegation and no routing of item work through other roles
  (code-mapper, data-flow-tracer) — on codex/zcode the implementer performs its
  own research, chooses the solution, implements, runs local checks, and reworks
  within the package.
- [ ] Comment cleanliness (the release gate's traceability rule, integrate-release
  Step 3.5): the implementer package carries the rule — comments may reference
  decisions only via `D##` of `.ai/DECISIONS.md`; spec refs (`C##`, `R##`, `A##`,
  `X##`, «ТЗ …», «этап N»), narrative comments, multi-line function descriptions,
  TODO/FIXME, and debug leftovers must not be left in the diff; a one-sentence
  public API docstring is allowed. Violations surface at I5 as rework remarks —
  do not fix an implementer's comments silently.
- [ ] Time budget of sub-agent commands (`.ai/TESTS_CONFIG.md`): every implementer
  check command is wrapped in `timeout 150` with output to a file and no pipe; a
  pytest process past 200 s is a hang (Windows post-test teardown), not a slow
  check — the implementer kills it, reads the results from the file, and reports
  it as a hang. The rule is fixed in the role definitions; when accepting reports,
  verify `timeout 150` in the Checks commands and never accept a silently raised
  limit.
- [ ] Receive each report as its implementer returns: changed files, solution
  summary, checks with real exit codes (`references/agent-orchestration.md`,
  Report Check). On codex/zcode the report carries the seven sections — Result,
  Research, Changed Files, Solution Summary, Criteria Mapping, Checks, Open
  Questions — with the implementer's own findings in Research. Store it in the
  run directory; update the state file.
- [ ] As each implementer returns, proceed to that item's I5 without waiting for
  the whole wave — claude: the item's acceptance tester launches; zcode: the
  item's single independent acceptor launches; codex: the main agent accepts the
  item personally.

## Checklist (non-code item — claude)

- [ ] The main agent performs the action itself (spec maintenance, run reports,
  running checks, git commands) within the item boundaries
  (`references/stage-implementation.md`, Division of Labor) at a wave boundary.
- [ ] Record what was done and how it was verified in the state file.

On codex/zcode there is no separate non-code path for checklist items: docs and
configuration items follow the same single-implementer checklist above with the
package prepared in I2; only run bookkeeping (statuses, reports, checks, git
commands) stays with the main agent.

## Result

Changes of the wave's items only (by the implementers, or the main agent's own
non-code actions) plus a report with check results per item.

## Transition

- Per item: proceed to I5 as soon as its implementer returns.
- Implementer reports `blocked` → analyze the reason: package contradiction,
  missing dependency, unavailable model. Fix the package or research and relaunch
  the same role, or STOP with the reason; the rework counter is not reset
  (`references/task-package.md`). A blocked item does not pause independent
  siblings of its wave.
