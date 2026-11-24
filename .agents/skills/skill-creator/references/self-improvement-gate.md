# Self-Improvement Gate

Use this reference before changing any existing skill, including `skill-creator` itself.

## Decision Flow

1. **Observation:** What happened? Is it a reusable lesson, a failure, or a requested behavior change?
2. **Target:** Which file should change?
   - `LEARNINGS.md` for reusable lessons.
   - `EVALS.md` for failures and regression expectations.
   - `references/` for detailed guidance.
   - `SKILL.md` only for contract, routing, algorithm, or critical behavior changes.
3. **Eval:** If `SKILL.md` behavior changes, add or update an eval-case first.
4. **Patch:** Replace, remove, or move guidance before appending new rules.
5. **Validate:** Check the quality gate and relevant eval expectations.

## Patch Criteria

Patch `SKILL.md` only when at least one is true:

- The existing algorithm causes repeated failure.
- The trigger or entry/exit contract is wrong.
- The skill cannot find required supporting context.
- A rule is ambiguous and the ambiguity affects output.
- A supporting file exists but is not discoverable from `SKILL.md`.

Do not patch `SKILL.md` when the change is only a one-time lesson, a project-specific exception, or detailed background better stored in `references/`.

## Eval Case Requirements

An eval-case should include:

- A stable ID (e.g. `SC-EVAL-001`) that survives rewording and renumbering of other cases.
- `Given`: starting condition or user request (the situation).
- `Expected`: observable behavior.
- Optional `Failure mode`: what must not happen.
- Optional `Files touched`: expected files or directories.

Keep evals small. They should protect behavior, not become a second specification. Do not delete an active eval case without user agreement.

## Learning Memory Budgets and Candidates

`LEARNINGS.md` and `EVALS.md` are short-format memory with per-file token budgets resolved from `.ai/workflow.yaml` (defaults 2500 tokens each, per-skill overrides possible). `max_chars` is not a memory limit. See `rules/skills.md` for the full policy.

### Reading Memory

- A normal run reads the skill's `LEARNINGS.md` fully.
- `EVALS.md` is loaded only to check or change behavior, to analyze an error, or when an instruction references it directly.
- No per-source-file memory and no mandatory learning sub-agent; existing roles collect lessons within their own boundaries.

### Before Adding a Lesson

1. Draft the lesson as a short reminder; merge duplicates and replace obsolete wording instead of appending contradictions.
2. If the resulting file fits its token budget, update it normally.
3. If it does not fit, keep the acting file unchanged, save the compressed candidate to `.ai/memory-candidates/<skill>.md`, and propose the composition or a limit to the user.
4. Never delete a unique lesson or an active eval case without user agreement.

### Candidate Handling

Candidates are not auto-loaded, survive run-directory cleanup, and are removed after the user decision.

### Validation

Run `uv run python scripts/validate_skill_memory.py` for an advisory JSON report: per-file token count, limit, and status. Over-budget files produce WARN findings with exit code 0. There are no format findings for missing tables or Retrieval Rules sections.
