# Spec Examples

Use examples when the correct shape is unclear. Do not copy content blindly; copy structure and specificity.

## Feature Example

```markdown
# Skill Supporting Files — Specification (v0.4.0)

> **Дата создания:** 2026-05-13
> **Ветка:** `feature/v0.4.0-skill-supporting-files`
> **Статус:** В работе
> **Standard:** validate-requirements-ieee29148 | Score: 88/100

## Видение

Workflow skills should keep `SKILL.md` short and route detailed context to directly linked supporting files.

## Архитектурные решения

| # | Вопрос | Решение |
|---|--------|---------|
| Q1 | Where to store detailed checklists? | In `references/`, one-level deep from `SKILL.md`. |

## Требования

| ID | Требование | Обоснование | Проверка |
|---|---|---|---|
| R1 | SKILL.md does not embed detailed instructions | Readability of the skill contract | Inspection of SKILL.md: no embedded question banks |
| R2 | Supporting files are reachable by a direct link from SKILL.md | Navigation without chains | Every instruction is referenced directly in SKILL.md |

## Этапы реализации

### ⬜ Этап 1: Restructure skill context

**Файлы:**
- `skills/plan-release/SKILL.md`
- `skills/plan-release/references/scope-discovery.md`

**Что делаем:**
Move detailed ASQ guidance from `SKILL.md` to a focused reference file.

- [ ] C1.1 [R1] Move the ASQ question bank to `references/scope-discovery.md`.
- [ ] C1.2 [R2] Add a direct link to the new reference in SKILL.md.

**Зависимости:** none

**Определение готовности:** `SKILL.md` lists the reference directly and no longer embeds the full ASQ question bank.

**Проверка:** inspection of SKILL.md; `validate_spec_structure.py` — PASS.
```

## Bugfix Example

```markdown
# Bugfix Spec Validation — Specification (v0.4.1)

> **Дата создания:** 2026-05-13
> **Ветка:** `bugfix/v0.4.1-spec-validation`
> **Статус:** В работе
> **Standard:** validate-requirements-ieee29148 | Score: 90/100

## Видение

Specs with missing workflow tables should fail before branch creation.

## Архитектурные решения

| # | Вопрос | Решение |
|---|--------|---------|
| Q1 | Check manually or with a script? | With a script, to rule out accidental omissions. |

## Требования

| ID | Требование | Обоснование | Проверка |
|---|---|---|---|
| R1 | Structural check runs before branch creation | Errors are caught before being fixed in git | Validator run and PASS before branch/commit |

## Этапы реализации

### ⬜ Этап 1: Add structural validator

**Файлы:**
- `skills/plan-release/scripts/validate_spec_structure.py`

**Что делаем:**
Validate required sections and workflow rows.

- [ ] C1.1 [R1] Add a check for required sections and workflow rows.

**Зависимости:** none

**Определение готовности:** Validator exits with non-zero status when required sections are missing.

**Проверка:** run the validator on a spec without a workflow table — non-zero exit code.
```

## Document/Research Example

```markdown
# Literature Review Update — Specification (v0.4.0)

> **Дата создания:** 2026-05-13
> **Ветка:** `feature/v0.4.0-literature-review-update`
> **Статус:** В работе
> **Standard:** {confirmed-document-standard} | Score: manual-pass

## Видение

The literature review should reflect current supporting-file best practices and distinguish hard findings from heuristics.

## Архитектурные решения

| # | Вопрос | Решение |
|---|--------|---------|
| Q1 | Use IEEE? | No, this is a document task; the standard is confirmed by the user. |

## Требования

| ID | Требование | Обоснование | Проверка |
|---|---|---|---|
| R1 | The review distinguishes hard findings from heuristics | The reader will not mistake a heuristic for a fact | Inspection of the review sections |

## Этапы реализации

### ⬜ Этап 1: Update review content

**Файлы:**
- `docs/literature-review.md`

**Что делаем:**
Rewrite the findings section using the confirmed document standard.

- [ ] C1.1 [R1] Split findings into confirmed and heuristic, with sources indicated.
```
