# P1. Entry And Boundaries

Load this file right before performing P1; later sub-steps are not preloaded.
Performed by the main agent; no sub-agents in this sub-step.

## Inputs

- User request
- Git state (current branch)
- Project rules: `CLAUDE.md` / `AGENTS.md`, `.ai/DECISIONS.md`

## Checklist

- [ ] ENTRY: the current branch is `main` or `master`. Otherwise stop with a short
  message naming the condition; do not start planning on a feature branch.
- [ ] State the goal and the expected result of the request in one or two sentences.
- [ ] Classify the task: feature, bugfix, document/research, or mixed
  (`references/standard-selection.md`).
- [ ] Select the validation standard for the task type: code tasks use
  `validate-requirements-ieee29148`; document tasks ask the user which standard
  applies.
- [ ] Record immutable boundaries the spec must respect: product boundaries from
  `.ai/DECISIONS.md`, workflow rules, project constraints named by `CLAUDE.md` /
  `AGENTS.md`, and anything the user fixed in the request.
- [ ] When `.ai/specs/draft/next-release.md` exists, read it and carry its open
  candidates into planning as inputs for P2 re-verification; a missing file is
  not an error — proceed without a backlog and do not create the file at
  planning time (Release Candidate Backlog in `references/scope-discovery.md`).
- [ ] Do not create the branch and do not write the spec file yet.

## Result

Entry allowed; task type and standard recorded; immutable constraints listed;
open release-backlog candidates carried forward when the backlog file exists.

## Transition

- Proceed to P2 (context collection) carrying the recorded boundaries.
- If entry is not allowed (wrong branch, unfinished release state), stop; the user
  decides how to proceed.
