# Evals — skill-creator

Regression cases for changes to `skill-creator`. Add a case before changing `SKILL.md` behavior.

## SC-EVAL-001 — New Skill Has Self-Improvement Files

**Given:** User asks to create a new workflow skill.

**Expected:**
- `skills/{name}/SKILL.md` exists.
- `skills/{name}/LEARNINGS.md` exists.
- `skills/{name}/EVALS.md` exists.
- `SKILL.md` contains Continuous Improvement or equivalent Improvement Triage.

## SC-EVAL-002 — Supporting Files Are One-Level Deep

**Given:** User asks for a skill with detailed context or runbooks.

**Expected:**
- `SKILL.md` directly lists relevant `references/`, `scripts/`, or `assets/`.
- No required navigation chain depends on `reference-a.md -> reference-b.md`.
- Detailed context that is not needed on every run is outside `SKILL.md`.

## SC-EVAL-003 — Behavioral Patch Requires Eval

**Given:** User asks to change an existing skill's behavior.

**Expected:**
- The failure or new expected behavior is represented in `EVALS.md`, unless the assistant explicitly states why a manual-only eval is appropriate.
- `SKILL.md` patch is minimal and replaces, removes, or moves guidance rather than simply appending more rules.

## SC-EVAL-004 — Claude Target Is Preserved

**Given:** Local workspace contains adapter-specific paths such as `.agents/skills/`.

**Expected:**
- `skill-creator` still treats `skills/` as dot_ai source of truth.
- Installation guidance remains oriented to `.claude/skills/`.
- The assistant does not "fix" paths to non-Claude adapters unless the user explicitly requests it.

## SC-EVAL-005 — Short Memory Format Is Accepted

**Given:** A skill's `LEARNINGS.md` holds short reminder bullets without a lessons table and without a Retrieval Rules section.

**Expected:**
- `scripts/validate_skill_memory.py` emits no format findings for that file and reports only its token count against its per-file limit.
- No WARN asks for a table, a Retrieval Rules section, or mandatory condition/reason/link columns.
- `max_chars` plays no role in the memory audit; budgets come from `.ai/workflow.yaml` (defaults 2500 tokens per file, per-skill overrides possible).

## SC-EVAL-006 — EVALS Loaded Only For Behavior Work

**Given:** A routine `skill-creator` run that only creates or updates supporting content, and a run that changes `SKILL.md` behavior.

**Expected:**
- The routine run reads the skill's `LEARNINGS.md` fully and does not load `EVALS.md`.
- The behavior-changing run reads the applicable `EVALS.md` cases before the patch.
- No per-source-file memory and no mandatory learning sub-agent are introduced; existing roles collect lessons within their own boundaries.

## SC-EVAL-007 — Over-Budget Memory Becomes a Candidate

**Given:** New lessons for a skill whose `LEARNINGS.md` still exceeds its token budget after compressing wording and merging duplicates.

**Expected:**
- The acting `LEARNINGS.md` stays unchanged; no unique lesson or active eval case is deleted without user agreement.
- The compressed candidate is saved to `.ai/memory-candidates/<skill>.md` together with a proposed composition or limit for the user.
- The candidate is not auto-loaded, survives run-directory cleanup, and is removed only after the user decision.
