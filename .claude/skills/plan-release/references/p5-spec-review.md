# P5. Review

Load this file right before performing P5. The reviewer sub-agent checks the
document; the main agent evaluates findings and fixes the spec itself.

## Inputs

- Draft spec from P4
- Project architecture and decision documents
- Active validation standard with its threshold

## Checklist

- [ ] Apply `references/requirements-quality.md` yourself first; fix what is
  clearly weak before involving a sub-agent.
- [ ] Choose the reviewer level per `references/model-selection.md` and record
  the choice with its reason — claude: middle level by default, senior level
  when complex-level signs are present; codex/zcode: the fixed supported model
  of the host, a single profile regardless of complexity.
- [ ] Compose the reviewer package (`references/task-package.md`): `repo_root`,
  `spec_path`, `standard` with threshold, `project_context` (architecture and
  decision documents), `review_scope`.
- [ ] Launch the spec reviewer role with the package only — Codex: role
  `workflow_spec_reviewer` at `gpt-6.1-sol` + `low` (single profile; no
  separate complex variant); Claude: sub-agent `workflow-spec-reviewer` with
  the model from `references/model-selection.md` (middle level by default;
  senior level when complex-level signs are present); ZCode: a
  general-purpose sub-agent with the reviewer contract restated from
  `templates/agents/workflow-spec-reviewer.md` (complex-level signs: the
  restated contract demands a full-depth review).
- [ ] Evaluate every finding yourself against the spec and the project documents;
  fix the document yourself; the reviewer never edits and never decides scope.
- [ ] Store the reviewer package, the report, and your verdict record
  (accepted | rework | blocked; checked criteria; attempt number) in the run
  directory (`references/task-package.md`, `references/run-artifacts.md`).
- [ ] Run the active standard validation: `validate-requirements-ieee29148` for
  code specs; pass threshold ≥85. Document tasks use the standard confirmed in P1.
- [ ] Run `scripts/validate_spec_structure.py {spec-path}` and fix the document
  until it prints PASS.

## Result

Accepted spec: reviewer findings resolved, standard score ≥ threshold, structural
validation PASS.

## Transition

- Proceed to P6 (completion).
- A low-quality reviewer answer follows the acceptance loop of
  `references/task-package.md`: concrete rework remarks, at most two
  returns, then the user decides; no silent model change.
