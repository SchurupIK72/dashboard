# Scope Discovery

Use this reference before writing a spec. The goal is to expose decisions that would otherwise be guessed.

## When To Ask

Ask the user when the answer changes:

- scope boundaries
- architecture or data flow
- user-visible behavior
- API, CLI, or file format contracts
- migration, compatibility, or rollout
- acceptance criteria or Definition of Done
- risk posture: security, performance, reliability, privacy
- answer contradicts or expands product boundaries in `.ai/DECISIONS.md`

Do not ask questions whose answer only changes wording.

**Exhaustive ASQ policy:** ask about all ambiguities, including those with a safe default, if the decision affects scope. Do not silently accept a safe default when the choice influences what the spec covers.

## Reusing Earlier Decisions

Re-applying an earlier answer is governed by `policies.interview.repeat_confirmed_general` in `.ai/workflow.yaml`:

- Reuse only a decision explicitly confirmed as general — recorded in `.ai/DECISIONS.md` or the permanent `.ai/workflow.yaml` by meaning — and only when its area and conditions match; record the source (file and entry) with the decision.
- A one-off answer stays one-off; generalizing it needs an explicit user confirmation, recorded once in `.ai/DECISIONS.md` (product boundaries) or the permanent YAML (settings) — never copied into a second active source.
- Changed conditions or a conflict with a recorded decision is a scope question: raise it as one ASQ round instead of overriding or stretching the record.

## Release Candidate Backlog

The backlog file `.ai/specs/draft/next-release.md` holds user-owned candidates
for future releases: a stable `BUG-<n>` or `FEAT-<n>` ID, the symptom with the
expected behavior or the benefit, source, environment, date, and status. A
backlog entry is an idea, never a requirement — only an explicit interview
decision moves a candidate into the spec.

- P1 reads the file when it exists and carries open candidates into planning; a
  missing file is not an error and is never created at planning time.
- P2 re-verifies every open candidate against the current code — still relevant,
  already implemented, or obsolete — recording file/symbol evidence per
  candidate.
- P3 selects candidates explicitly, one candidate per ASQ round, with three
  outcomes: include in the spec, keep open, or reject with a dated reason.
  Silence, a safe default, or elapsed waiting time never selects a candidate;
  an unconfirmed idea stays out of the spec.
- P4 records the selected-candidate to requirement-ID mapping in the working
  notes for the completion write-back.
- P6 updates the backlog once after the successful commit: absorbed entries get
  `absorbed <date>` plus the requirement ID and the spec path; rejected entries
  get `rejected <date>` plus the reason; unselected entries stay open. Entries
  are never deleted or renumbered, IDs are never reused, and a run without a
  completed commit leaves the backlog untouched.
- The file is user-owned: installation creates it once from the template and
  never overwrites it, and cleanup never touches it. A new idea the user voices
  but does not select is appended with the next free ID only on explicit user
  confirmation.

## Question Bank

### Outcome

- What exact user or project outcome should exist after this spec is implemented?
- What current pain or failure does this change remove?
- How will we know the change is successful?

### Scope Boundaries

- What is explicitly in scope?
- What is explicitly out of scope for this iteration?
- Are there related workflows that must stay unchanged?
- Is this a one-off change or a reusable capability?

### Product Behavior

- What should happen by default?
- What should happen for empty, missing, invalid, or conflicting input?
- Who is the user or actor for the behavior?
- Does the change need a new command, file, API endpoint, UI control, or workflow step?

### Technical Boundaries

- Which modules, skills, rules, templates, or docs are expected to change?
- Is backward compatibility required?
- Are migrations, config changes, or install changes needed?
- Are there external services, credentials, or environment assumptions?

### Quality And Tests

- What acceptance criteria are objective enough to test?
- Which tests or checks should prove the behavior?
- Is a manual verification step acceptable?
- What failure mode must not regress?

### Rollout And Risk

- Can the change be delivered in one stage?
- Does it need feature flags, fallback, rollback, or staged rollout?
- What is the highest-risk assumption?
- What would make this spec too broad?

### Decisions Alignment

- Does this requirement conflict with any IS NOT boundary in `.ai/DECISIONS.md`?
- Does this requirement introduce scope not covered by any IS boundary?
- Is the expansion of product boundaries intentional or accidental?
- Should a new IS/IS NOT entry be added to DECISIONS.md?

## ASQ Output Shape

ASQ always asks exactly one question per round. Do not group multiple questions in one request, even when several open decisions exist.

Pick the highest-impact unresolved decision first:

1. Blocks writing a correct spec.
2. Changes scope, architecture, UX/API, or Definition of Done.
3. Has no safe default.
4. Would cause the largest rework if guessed incorrectly.

```markdown
Need to clarify scope before writing the spec:

{One question}

Why it matters: {impact}
Suggested default: {default, if safe}
```

After the user answers:

1. Record the decision in working notes for the spec, with its origin — one-off for this spec, or explicitly confirmed general with its source.
2. Re-evaluate whether another ambiguity remains — including non-blocking ones where a safe default exists but the choice affects scope.
3. If yes, ask the next single question in a new ASQ round.
4. If no ambiguity remains, write the spec and record decisions in `Архитектурные решения` and consequences in `Этапы реализации`.

## When The User Does Not Answer

`policies.interview.unanswered` in `.ai/workflow.yaml` sets what is allowed while a significant question stays open. In the `independent_work_only` mode, only independent research and a draft where the open point is an explicit assumption proceed; dependent changes and the final acceptance of that decision wait for the answer. Waiting time or a `default` mark is not consent, and the draft never presents the assumption as the owner's decision.
