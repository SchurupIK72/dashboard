---
name: plan-release
description: >
  Workflow step ①: release planning — creating the spec + branch + commit.
  Triggers: "создай ТЗ", "new feature", "новая фича", "bugfix", "исправь баг",
  "spec-creation", "plan release", "запланируй релиз".
  Automatically selects the validation standard by task type
  (IEEE 29148:2018 for code, another one for documents).
  After validation, creates a feature/* or bugfix/* branch and commits the spec.
---

# Plan Release Skill

**Workflow step ①** — release planning: creating the spec, validating against the selected standard, branch and commit.

## Workflow Contract

```yaml
entry:
  branch: main | master
  trigger:
    - "создай ТЗ"
    - "new feature"
    - "новая фича"
    - "bugfix"
    - "исправь баг"

exit:
  artifacts:
    - .ai/specs/{branch-type}-v{version}-{slug}.md
  branch: feature/v{version}-{slug} | bugfix/v{version}-{slug}
  commit: "docs: add spec for {feature-name}"

next_skill: implement-spec-stage

uses:
  - validate-requirements-ieee29148
```

## Sub-stages

Load a sub-stage's instruction immediately before executing it; the whole set is not loaded in advance. The main agent accepts a sub-stage's result before the next one begins.

| # | Sub-stage | Instruction | Result and transition condition |
|---|---|---|---|
| P1 | Entry and scope | `references/p1-entry-scope.md` | Entry allowed; task type, standard, immutable constraints, and open release-backlog candidates recorded |
| P2 | Context gathering | `references/p2-context-research.md` | Facts, files, dependencies, and gaps accepted by the main agent |
| P3 | Interview | `references/p3-interview.md` | Decisions recorded with origin and source; no significant open questions, or explicit draft assumptions waiting for answers |
| P4 | Spec | `references/p4-spec-authoring.md` | Spec draft: requirement IDs, domain checklists, traceability |
| P5 | Review | `references/p5-spec-review.md` | Remarks assessed and fixed; standard not below the threshold; structural check PASS |
| P6 | Completion | `references/p6-completion.md` | Branch and commit created; result and `next_skill: implement-spec-stage` |

Missing facts identified during the interview send the flow back to P2–P3; such a return does not count as a failed sub-agent attempt. Returning a single sub-agent result for rework is limited to two times (R17).

## Supporting Files

| File | When to read or run | Purpose |
|---|---|---|
| `LEARNINGS.md` | At the start of a run | Only lessons from previous runs relevant to the current task |
| `references/p1-entry-scope.md` … `references/p6-completion.md` | Immediately before the corresponding sub-stage | Detailed sub-stage instructions (table above) |
| `references/task-package.md` | P2 and P5, before launching a sub-agent | Task package contract and result acceptance loop |
| `references/model-selection.md` | P2 and P5, when selecting a sub-agent model | Complexity table, recording the choice, model unavailability — stop |
| `references/run-artifacts.md` | P6, after a successful commit | Run directory, continuation, and limited cleanup |
| `references/scope-discovery.md` | In P3, before the interview | ASQ questions, scope, decision provenance, unanswered-question mode, readiness criteria, release-candidate backlog procedure |
| `references/standard-selection.md` | In P1, when the task type is not obvious | Standard selection for code, documents, and mixed tasks |
| `references/requirements-quality.md` | In P5, before validation | Criteria for good requirements and anti-patterns |
| `references/version-branching.md` | In P4 and P6, before creating the file, branch, and commit | Version, slug, spec file name, branch, commit message |
| `references/decisions-check.md` | In P2, when studying project context | Checking draft requirements against `.ai/DECISIONS.md` |
| `assets/spec-template.md` | In P4, when creating a new spec | Canonical spec template |
| `references/checklist-format.md` | In P4, when writing stage checklists | Item format, additions with a reason, diary prohibition |
| `references/examples.md` | When an example of a form or a debatable task subtype is needed | Canonical examples of feature, bugfix, and document/research specs |
| `scripts/validate_spec_structure.py` | In P5, after writing the spec | Deterministic spec structure check |
| `EVALS.md` | Before changing skill behavior | Regression cases for the eval gate |

## Algorithm

1. **Read relevant experience** — open `LEARNINGS.md` and apply only the lessons relevant to the current task.
2. **Execute sub-stages P1–P6 strictly in order** — before each sub-stage, load its instruction from the "Sub-stages" table; accept a sub-stage's result before moving to the next one.
3. **Output the P6 result** — the spec path, branch, commit, and the next step: `implement-spec-stage`.

## Validation Checklist

- [ ] ENTRY: the current branch is `main` or `master` (P1).
- [ ] Each sub-stage is executed per its instruction; its result is accepted before the next one begins.
- [ ] P3: ASQ asks exactly one question per round; re-applied decisions are explicitly confirmed general with a recorded source; without an answer to a significant question only independent research and a draft with explicit assumptions proceed, dependent work waits.
- [ ] Release backlog: existing `.ai/specs/draft/next-release.md` candidates are re-verified against the current code; only explicitly selected candidates enter the spec; absorbed entries receive the requirement and spec link on completion; unselected and rejected entries stay with date and reason; an unconfirmed candidate never becomes a requirement.
- [ ] P4: every requirement has an ID, rationale, and verification; every stage has files, dependencies, a definition of done, and an item checklist with references to requirement IDs.
- [ ] P5: the code-spec passed `validate-requirements-ieee29148` with score ≥85; `scripts/validate_spec_structure.py` prints PASS.
- [ ] P6: branch, spec title, file, and commit message follow `references/version-branching.md`; the version is the same everywhere; temporary files of the current run are deleted only after a successful commit (`references/run-artifacts.md`).

## Continuous Improvement

Upon completing each run, perform Improvement Triage:

1. Task solved without ambiguities → output `no_change`.
2. A reusable lesson discovered → add a brief entry to `LEARNINGS.md`.
3. Skill instructions led to an error → first create an eval case in `EVALS.md`.
4. Propose a `SKILL.md` patch only if the same problem can recur.
5. Prefer replacing, removing, or moving rules to a supporting file over simply adding rules.
6. Do not update `SKILL.md` until the corresponding eval passes.

## Rules

1. Do not write a spec based on implicit decisions: use exhaustive ASQ to resolve all ambiguities, including those where a safe default exists; check the spec against `.ai/DECISIONS.md` via `references/decisions-check.md`. Re-apply only explicitly confirmed general decisions with a recorded source; one-off answers stay one-off; without an answer to a significant question only independent research and a draft with explicit assumptions proceed (interview policy keys in `.ai/workflow.yaml`, protocol in `references/p3-interview.md`).
2. `SKILL.md` remains the contract and router; keep detailed context in directly linked supporting files.
3. Do not duplicate the IEEE 29148 standard here: use `validate-requirements-ieee29148` for code-specs.
4. Do not validate document and research tasks as code-specs without user confirmation.
5. Any behavioral change to the skill requires an eval case or explicit manual justification.
6. Do not create a spec without a future SemVer version in the title, file name, and branch.
7. The source of truth for the skill is `skills/plan-release`; the runtime copies (`.agents/skills/`, `.claude/skills/`) are synchronized from it and are not edited directly. Do not edit the skill inside an installed project: dot_ai is the source of truth.
8. Sub-stages P1–P6 are fixed: a sub-stage's instruction is read immediately before executing it, the whole set is not loaded in advance; skipping acceptance of a sub-stage's result is forbidden.
9. Sub-agents P2 (researcher) and P5 (spec-reviewer) deliver facts and remarks in the task package; the interview, scope decisions, and spec edits are performed only by the main agent with the user.
