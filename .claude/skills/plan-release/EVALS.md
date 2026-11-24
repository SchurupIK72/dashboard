# Evals — plan-release

Regression cases. Used as a gate before patching `SKILL.md`.

## SC-EVAL-001 — Hidden Scope Requires Questions

**Given:** User asks for a new feature with unclear behavior, API contract, edge case handling, or Definition of Done.

**Expected:**
- The skill reads `references/scope-discovery.md`.
- The skill asks exactly one question in the ASQ round.
- The question is the highest-impact unresolved decision whose answer changes the spec.
- The spec records answered decisions in `Архитектурные решения`.

**Failure mode:** The skill silently invents non-obvious scope decisions or asks multiple questions in one ASQ round.

## SC-EVAL-001B — ASQ Never Batches Questions

**Given:** User asks for a feature with three unresolved scope decisions.

**Expected:**
- The skill asks one question only.
- After the user answers, the skill may ask the next single question in a separate round.
- The skill does not use a numbered multi-question list.

**Failure mode:** The skill groups several questions into one message.

## Compact Cases

Stable ID, situation, expected behavior — the same regression gate as the section cases, kept compact for the memory budget.

| ID | Situation | Expected |
|---|---|---|
| SC-EVAL-002 | Code task: feature, bugfix, API, config, or workflow behavior change. | Select `validate-requirements-ieee29148`; metadata records standard and score; pass only with score ≥85; never a document-only standard for executable behavior. |
| SC-EVAL-003 | Docs-only task: review, guide, report. | Read `references/standard-selection.md`; ask which document standard applies when unspecified; no IEEE code validation without confirmation. |
| SC-EVAL-004 | A spec file has been written. | Run `scripts/validate_spec_structure.py {path-to-spec}`; missing sections, workflow rows, stage markers, or metadata are fixed before branch/commit completion. |
| SC-EVAL-005 | Additional detailed guidance is needed. | `SKILL.md` links the supporting file directly with a focused purpose-based name; no `SKILL.md -> reference-a.md -> reference-b.md` chains. |
| SC-EVAL-006 | New feature or bugfix spec. | One future SemVer version from `.ai/CHANGELOG.md` in title, filename, branch, and metadata; `feature-v{version}-{slug}.md` / `bugfix-v{version}-{slug}.md` artifacts; no old `bugfix/{version}-{slug}` convention. |
| SC-EVAL-007 | Planning run entered. | Fixed sequence entry → context → interview → spec → review → completion; each instruction loads right before its sub-step; a sub-step result is accepted before the next starts; interview returns to context are not failed attempts. |
| SC-EVAL-008 | Researcher and reviewer sub-agents run. | Sub-agents get task packages and return facts and remarks only; the main agent writes the spec and decides scope with the user; no sub-agent invents scope decisions. |
| SC-EVAL-009 | Draft spec ready for review. | Reviewer model per the complexity table with recorded rationale; explicit user assignment wins; an unavailable model stops the run with files preserved, no silent fallback. |
| SC-EVAL-010 | Run produces packages, reports, remarks. | Files live under `.ai/workflow-runs/<branch-slug>/plan-release/<plan-id>/<run-id>/`; cleanup only after accepted spec, branch, and commit, current run directory only; failure keeps files for resume. |
| SC-EVAL-020 | Release backlog `.ai/specs/draft/next-release.md` exists with open candidates. | Candidates are re-verified against the current code before any selection; each candidate is selected explicitly, one ASQ round per candidate; an unconfirmed candidate never enters the spec. |
| SC-EVAL-021 | Backlog candidate explicitly selected and the spec is committed. | The entry becomes `absorbed <date>` with the requirement ID and spec path; rejected entries carry a dated reason; unselected stay open; nothing is deleted, renumbered, or silently rewritten. |
| SC-EVAL-022 | Install or upgrade runs over an existing backlog file. | The file is created from the template only when absent; an existing user-owned backlog is never overwritten — user content survives byte-for-byte, history intact. |

## SC-EVAL-011 — Codex Carriers Carry No Claude Aliases

**Given:** `plan-release` prepares a sub-agent launch on Codex, and the Codex carriers of the skill (references, adapter mapping) and the Codex role profiles are read.

**Expected:**
- No `haiku`, `sonnet`, or `opus` alias appears in any Codex context of the skill or in the Codex role profiles.
- Every Codex launch states the explicit values `gpt-6.1-sol` and reasoning effort `low` — a single profile per function, regardless of complexity.
- The Claude column keeps its alias tiers; the example recording line is labeled as the claude-column example.

**Failure mode:** A Codex column or profile shows a Claude alias, a per-complexity Codex model split, or an unspecified model.

## SC-EVAL-012 — ZCode Implementer Profile Is Pinned

**Given:** A ZCode implementer launch is prepared from the product profile.

**Expected:**
- The profile frontmatter pins `model: account:zai-individual-coding-plan/GLM-5.3` and `thoughtLevel: max`.
- Roles without a pinned profile are dispatched as general-purpose sub-agents with the role contract restated from the product role files.
- No unconfirmed generation-token or length parameters are invented alongside the pinned values.

**Failure mode:** The implementer launched without the pinned model or thought level, or with invented output settings.

## SC-EVAL-013 — Unavailable Model Or Isolation Blocks The Launch

**Given:** The researcher (context collection) or the spec reviewer model is unavailable, or an isolated sub-agent context cannot be created.

**Expected:**
- The dependent launch stops with an explicit blocking message naming the model and the reason.
- Run files are preserved; nothing is cleaned up.
- No silent fallback to another model, no substitution inside the skill, no change to the main agent model settings; resuming requires an explicit user decision.

**Failure mode:** The skill silently retries with another model or passes the full chat history instead of a package.

## SC-EVAL-014 — Implementer Templates Fix The Seven-Section Report

**Given:** The implementer role templates (the general role file, the Codex profile, the ZCode profile) are read.

**Expected:**
- Each template fixes the seven report sections: Result, Research, Changed Files, Solution Summary, Criteria Mapping, Checks, Open Questions.
- The report target is 3000 tokens with no character ceiling: over-target is marked, mandatory content is never truncated, detailed command output goes to the report paths.
- The package requires `item_baseline` and the execution fields (`dependencies`, `check_commands`, `time_budget`, `report_paths`), and a missing required field returns `INSUFFICIENT_CONTEXT: missing {field_name}`.

**Failure mode:** A template omits a section, enforces a character budget, or answers a missing package field from imagination.

## SC-EVAL-015 — Planning Researcher Stands Alone

**Given:** The skill performs context collection and prepares the researcher launch.

**Expected:**
- The planning researcher remains a standalone role with a supported Codex model (explicit model and effort when no named profile exists) and a restated contract on ZCode.
- The `research_report` field appears only in the claude implementer contract; on codex/zcode the implementer researches itself and the package carries no researcher report.

**Failure mode:** Context collection collapses into the implementer on claude, or a Codex/ZCode implementer package demands a researcher report.

## SC-EVAL-016 — Host Policy Sections Distinguish Host Duties

**Given:** The AGENTS.md template with the host-policy sections is rendered or reviewed.

**Expected:**
- The codex section mandates exactly one implementer sub-agent per checklist item with no nested delegation and acceptance performed personally by the main agent, linking the Codex implementer profile.
- The zcode section names the implementer and the acceptance tester as the per-item pair, linking only the implementer profile.
- The claude section keeps the researcher→implementer→tester chain with the general role files.
- All three sections agree with the model policy: Codex — the fixed supported model with low effort; ZCode — the pinned implementer model; claude — alias tiers through user settings.

**Failure mode:** A host section prescribes nested delegation, links a role file that does not exist, or contradicts the model-selection reference.

## SC-EVAL-017 — General Decision Reused With A Source

**Given:** An earlier decision is recorded as explicitly confirmed general (`.ai/DECISIONS.md` or permanent `.ai/workflow.yaml`), with matching area and conditions.

**Expected:**
- Re-applied without re-asking; the source is recorded in `Архитектурные решения`.
- A one-off earlier answer is not reused as general.

**Failure mode:** Reuse without a recorded source, or a one-off answer silently generalized.

## SC-EVAL-018 — Conflict Or Changed Conditions Require A Question

**Given:** A candidate decision conflicts with a recorded one, or a previous answer's area/conditions changed.

**Expected:**
- Exactly one ASQ question asks how to resolve the mismatch.
- The record is not overridden or stretched without the user's answer.

**Failure mode:** Silent override of the record, or reuse under changed conditions.

## SC-EVAL-019 — Unanswered Question Allows Independent Work Only

**Given:** A significant interview question has no user answer.

**Expected:**
- Only independent research and a draft with an explicit assumption proceed.
- Dependent changes and final acceptance wait for the answer.
- Waiting time or a `default` mark is not consent.

**Failure mode:** Dependent implementation starts on an unconfirmed decision, or an assumption is presented as the owner's decision.
