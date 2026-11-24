# I2. Item Research / Package Preparation

Load this file right before performing I2 for the current wave. The sub-step's
semantics follow the host policy fixed in I1:

- **claude** — wave research: fresh researcher sub-agents, one per code item of
  the wave, investigate the actual repository state; the main agent accepts
  each report individually before any implementer is assigned.
- **codex / zcode** — package preparation: no separate research phase and no
  researcher sub-agent for any item, docs and configuration included; the main
  agent composes one implementer package per item, and the implementer performs
  the research itself inside the implementation.

## Inputs

- The wave's items (ID, verbatim text), their requirements and acceptance criteria
- Stage file list and boundaries from the spec
- Repository at the current commit, including changes accepted from previous waves

## Checklist (claude: wave research)

- [ ] Read the item context yourself per `references/context-gathering.md` (spec
  section, requirements, allowed files, decision boundaries) for every item of the
  wave.
- [ ] Make the package demand consumer search: researchers locate affected
  consumers and checks by changed symbols and contract literals/selectors in
  source, tests and harness — not file names only — per the Consumer Search
  Protocol in `references/stage-implementation.md`, and report applicable
  UI/slow/integration layers with justified exclusions.
- [ ] Compose one researcher task package per item
  (`references/task-package.md`); store them in the run directory.
- [ ] Launch the researchers of the wave in one parallel batch per
  `references/agent-orchestration.md` (adapter-specific launch forms live there) —
  with the package only, never the main chat history.
- [ ] Accept each report yourself as it returns: re-check claimed files and symbols
  against the repository; evaluate gaps through `references/sufficiency-gate.md`;
  unknowns stay marked as unknown, `NOT_FOUND` entries must state the creation
  location.
- [ ] Store the accepted reports next to their packages; update the state file
  (current sub-step, accepted materials). A rework return goes to the same
  researcher only; independent items of the wave are not paused.

## Checklist (codex / zcode: package preparation)

- [ ] Read the item context yourself (spec section, requirements, allowed files,
  decision boundaries) for every item of the wave — every item takes an
  implementer, docs and configuration included.
- [ ] Remind in the package that the implementer performs its own consumer
  search: affected consumers and checks are located by changed symbols and
  contract literals/selectors in source, tests and harness — not file names
  only — per the Consumer Search Protocol in
  `references/stage-implementation.md`; the report lists applicable
  UI/slow/integration layers with justified exclusions.
- [ ] Compose one implementer package per item (`references/task-package.md`,
  package contract fields): item requirements with acceptance criteria,
  boundaries and constraints, relevant user decisions, command budgets, plus
  `dependencies`, `check_commands`, and `report_paths` (lists explicit, `[]`
  when empty) — WITHOUT `research_report`; the implementer performs its own
  research. Capture `item_baseline` before assignment — the status, diff, and
  modified/untracked file list of the item's area — and store it with the package
  in the run directory (`references/run-artifacts.md`).
- [ ] Update the state file (current sub-step, packages composed). No researcher
  launch and no research acceptance happen; the completeness of the returned
  implementer report (research performed, checks with real exit codes) is checked
  by the main agent at acceptance, not here.

## Result

- claude: an accepted research report for every code item of the wave — edit
  sites, files and symbols, contracts, reference pattern, related tests, and
  consumers located by symbol/contract-literal search — without blocking gaps.
- codex/zcode: one implementer package for every item of the wave — package
  contract only, no research_report.

## Transition

- claude: all reports of the wave accepted → proceed to I3 for the wave.
- codex/zcode: packages of the wave composed → proceed to I3 for the wave.
- claude only — a non-code item runs no researcher and no implementer: the main
  agent performs the action and its acceptance itself at a wave boundary, records
  the result in the state file, marks `[x]` after acceptance.
- claude only — blocking gap → do not assign an implementer for that item; fix
  the package and relaunch the researcher, or STOP per the gate with a message
  to the user.
- claude only — incomplete report → acceptance loop of
  `references/task-package.md` (concrete remarks, at most two rework returns).
- claude only — researcher model unavailable → STOP per
  `references/model-selection.md`.
