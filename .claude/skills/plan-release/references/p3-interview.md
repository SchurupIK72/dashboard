# P3. Interview

Load this file right before performing P3. Performed by the main agent with the
user; sub-agents do not interview and do not decide scope.

## Inputs

- User request
- Accepted context and gap list from P2

## Checklist

- [ ] Read `references/scope-discovery.md`.
- [ ] Ask exactly one question per ASQ round; every question must be a decision
  that changes scope, architecture, user-visible behavior, contracts, or the
  Definition of Done.
- [ ] Record every answered decision with its origin — one-off for this spec,
  or explicitly confirmed general; decisions the spec must carry are written to
  «Архитектурные решения» in P4.
- [ ] Re-applied decisions are explicitly confirmed general with their source
  recorded (see Decision Provenance); one-off answers stay one-off.
- [ ] Apply the exhaustive ASQ policy: ask about all ambiguities that affect
  scope, including ones with a safe default.
- [ ] Stop asking when no significant unresolved question remains.
- [ ] With an unanswered significant question, keep only independent research
  and a draft with explicit assumptions moving; dependent decisions wait (see
  Unanswered Significant Question).
- [ ] If an answer needs a repository fact not yet collected, return to P2 for
  that fact; the return is not counted as a failed sub-agent attempt.
- [ ] Select release-backlog candidates explicitly, one candidate per ASQ round,
  after the P2 re-verification: include in the spec, keep open, or reject with a
  dated reason. An unconfirmed candidate never enters the spec, and unselected
  candidates stay open (Release Candidate Backlog in
  `references/scope-discovery.md`).

## Decision Provenance

Reuse of earlier decisions is governed by `policies.interview.repeat_confirmed_general`
in `.ai/workflow.yaml`:

- When reuse is enabled, re-apply an earlier decision only if it was explicitly
  confirmed as general — recorded in `.ai/DECISIONS.md` or in the permanent
  `.ai/workflow.yaml` by meaning — and its area and conditions match the current
  task. Record the source (file and entry) in the working notes, then in
  «Архитектурные решения».
- A one-off answer applies to its spec only and never becomes general on its
  own. Generalizing it requires an explicit user confirmation recorded once:
  product boundaries in `.ai/DECISIONS.md`, settings values in the permanent
  YAML — no copies of the same values into a second active source.
- Changed conditions or a conflict with a recorded decision is itself a scope
  question: ask it as a single ASQ round instead of overriding or stretching
  the record.
- No separate decision registry is kept: the reusable records are
  `.ai/DECISIONS.md` and the permanent YAML; existing roles collect lessons
  within their own boundaries.

## Unanswered Significant Question

What is allowed without an answer is governed by `policies.interview.unanswered`
in `.ai/workflow.yaml`. In the `independent_work_only` mode:

- Independent research (P2 returns) and a spec draft that carries the open
  point as an explicit assumption remain allowed.
- Dependent changes and the final acceptance of the unconfirmed decision wait
  for the user's answer; an accepted spec never presents an assumption as the
  owner's decision.
- Waiting time and a `default` mark are not consent; only an explicit answer
  confirms the decision.

## Result

Fixed decisions, each with its origin and source; no significant open
questions, or explicit draft assumptions waiting for user answers.

## Transition

- Proceed to P4 (spec writing).
- A decision that contradicts or expands `.ai/DECISIONS.md` is resolved with the
  user first; the expansion is recorded in «Расширение решений проекта».
