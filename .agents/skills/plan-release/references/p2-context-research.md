# P2. Context Collection

Load this file right before performing P2. The researcher sub-agent collects
repository facts; the main agent reads project documents and accepts the report.

## Inputs

- Task type, standard and boundaries from P1
- Repository at the current base commit

## Checklist

- [ ] Read the project documents yourself: `.ai/ARCHITECTURE.md`,
  `.ai/CHANGELOG.md`, `.ai/DECISIONS.md` (`references/decisions-check.md`).
- [ ] Compose the researcher task package (`references/task-package.md`). For
  planning research the stage fields carry: `spec_path` — the planned path of the
  future spec; `stage_id` — `plan`; `checkbox_id` — `P2-research`; `item_text` —
  the research question derived from the P1 goal; `requirements` — facts to
  verify; `allowed_files` — the read scope. Include `architecture_constraints`
  from P1.
- [ ] Create the run directory `.ai/workflow-runs/plan-release/{plan-id}/{run-id}/`
  — plan-id is a short kebab-case slug of the request topic — and store the
  package there; keep a short state file at the run root: current sub-step,
  accepted materials, chosen models, rework counters
  (`references/run-artifacts.md`).
- [ ] Launch the researcher role with the package only, never the main chat
  history — Codex: role `workflow_researcher` at `gpt-6.1-sol` + `low` (named
  profile when one exists; otherwise pass the model, the reasoning effort, and
  the researcher role text explicitly — never inherit the main agent's
  reasoning settings); Claude: sub-agent `workflow-researcher`, model chosen
  per `references/model-selection.md`; ZCode: a general-purpose sub-agent with
  the researcher contract restated from `templates/agents/workflow-researcher.md`.
- [ ] Accept the report yourself: re-read the claimed files and symbols; record
  accepted facts, dependencies and contracts; unknowns stay marked as unknown,
  `NOT_FOUND` entries state the creation location; store the accepted report next
  to its package.
- [ ] Turn discovered gaps and unknowns into candidate interview questions for P3.
- [ ] Re-verify every open release-backlog candidate against the current code:
  include the candidate list in the researcher package read scope, then record a
  per-candidate verdict — still relevant, already implemented, or obsolete —
  with file/symbol evidence (Release Candidate Backlog in
  `references/scope-discovery.md`).

## Result

Accepted facts: files, symbols, dependencies, contracts; an explicit list of gaps
and unknowns; per-candidate backlog verdicts with evidence when the release
backlog exists.

## Transition

- Proceed to P3 (interview).
- If the researcher model is unavailable, stop per `references/model-selection.md`:
  blocking message naming the model, run files kept, no silent fallback.
- An incomplete report follows the acceptance loop of `references/task-package.md`
  (concrete remarks, at most two rework returns).
