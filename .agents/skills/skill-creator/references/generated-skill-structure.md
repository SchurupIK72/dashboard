# Generated Skill Structure

Use this reference when creating a new skill or doing a large restructuring.

## Directory Layout

```text
skills/{skill-name}/
├── SKILL.md
├── references/
│   └── {focused-topic}.md
├── scripts/
│   └── {validator-or-helper}
├── assets/
│   └── {template-or-static-resource}
├── LEARNINGS.md
└── EVALS.md
```

Create only the supporting directories that are useful for the skill. `LEARNINGS.md` and `EVALS.md` are always required.

## SKILL.md Contents

`SKILL.md` should contain:

1. Frontmatter: `name`, `description`, `type`, and `step` for workflow skills.
2. One-paragraph purpose.
3. Workflow Contract for workflow/internal skills.
4. Supporting Files table with direct links to useful files.
5. Short algorithm for the normal path.
6. Validation checklist.
7. Continuous Improvement block.
8. No more than 7 behavioral rules.

## Supporting File Rules

- `references/`: detailed checklists, rubrics, runbooks, edge cases, examples that are not needed on every run.
- `scripts/`: deterministic validators, generators, converters, or repeated checks.
- `assets/`: templates, static examples, images, or data.
- Keep references one-level deep from `SKILL.md`.
- Give files purpose-based names: `requirements-quality.md`, `merge-safety.md`, `deploy-rollback.md`.

## LEARNINGS.md Template

```markdown
# Learnings — {skill-name}

Short reminders, one or two lines each. No mandatory table, no mandatory sections.

- {Short repeatable lesson.}
- {Short repeatable lesson.}
```

Budgets are per-file tokens from `.ai/workflow.yaml`; if a new lesson does not fit, save a candidate to `.ai/memory-candidates/{skill-name}.md` and propose the composition or limit to the user instead of overwriting the acting file.

## EVALS.md Template

```markdown
# Evals — {skill-name}

Regression cases for behavior changes.

## {SKILL}-EVAL-001 — {Case Name}

**Given:** {starting condition}

**Expected:**
- {observable result}
- {observable result}
```

The eval ID is stable: it survives rewording and is never deleted without user agreement.
