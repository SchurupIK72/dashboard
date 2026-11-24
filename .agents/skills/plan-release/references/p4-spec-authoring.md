# P4. Spec Writing

Load this file right before performing P4. The main agent writes the spec;
sub-agents do not write or edit it.

## Inputs

- Fixed decisions from P3
- Accepted context from P2
- `assets/spec-template.md`

## Checklist

- [ ] Determine version and names per `references/version-branching.md`: the same
  `MAJOR.MINOR.PATCH` goes into the title, the spec filename, and the future
  branch.
- [ ] Write the spec from the template: metadata, `Workflow выполнения`,
  «Видение», «Архитектурные решения», «Требования», «Этапы реализации».
- [ ] Give every requirement a stable ID (`R1`, `R2`, …) with a rationale and a
  verification method — one requirement is stated once, in the requirements
  table.
- [ ] Build stages with files, dependencies, and an objective Definition of Done.
- [ ] Give every stage a checklist of items in the compact format
  (`references/checklist-format.md`):
  `- [ ] C{stage}.{n} [R..] action` — every item references existing requirement
  IDs and carries nothing but the action.
- [ ] Necessary extra work discovered while writing becomes a NEW open item with
  its own ID and a one-line reason (`- [ ] C2.4 [R05] action — reason`); it is
  never silently folded into an existing item.
- [ ] When release-backlog candidates were selected at the interview, record the
  candidate-to-requirement-ID mapping in the working notes — P6 uses it for the
  backlog write-back (Release Candidate Backlog in
  `references/scope-discovery.md`).

## Result

Draft spec at `.ai/specs/{branch-type}-v{version}-{slug}.md`.

## Transition

Proceed to P5 (review). The draft is not committed and its branch is not created
yet.
