# Context Gathering

Use this reference in I2 under the claude policy, when composing the researcher
package for the current item. Context is gathered per item, not once per stage:
every code item gets a fresh look at the current repository state, which includes
changes accepted from previous items.

On codex/zcode there is no researcher package: the main agent still reads the item
context itself — spec section, requirements, allowed files, decision boundaries —
before composing the implementer package per `references/task-package.md`.
Locating edit sites, symbols, contracts, and related tests in the actual files is
the implementer's Research section, not the main agent's work.

## What The Main Agent Reads Itself

Before composing the package, read:

- the checklist item wording and its stage section in the spec
- the related requirement IDs and their acceptance criteria from `## Требования`
- the stage file list — it becomes the basis of `allowed_files`
- boundaries from the spec and `.ai/DECISIONS.md` relevant to the item
- `.ai/ARCHITECTURE.md` when the item touches application code or contracts

Re-read the spec section for each item instead of relying on memory of a previous
item: the working copy may have changed, and an accepted previous item may have
shifted the plan.

## What Goes Into The Researcher Package (claude)

Follow `references/task-package.md`. Item-specific fields:

- `checkbox_id`, `item_text` — taken verbatim from the spec
- `requirements` — the requirement IDs named by the item plus their acceptance criteria
- `allowed_files` — the stage file list narrowed to what this item may touch
- `architecture_constraints` — boundaries that apply to these files
- `accepted_materials` — links to accepted packages/reports of earlier items when
  this item builds on them

Locating edit sites, symbols, contracts, analogous patterns, and related tests in
the actual files is the researcher's job, not the main agent's; the report format is
fixed in the role definition.

## Target File Handling

For each file in `allowed_files`:

- If it exists, the researcher reads it before proposing changes; verify with
  `git ls-files` when in doubt.
- If it does not exist, the report must carry `NOT_FOUND: {path}` with the exact
  creation location; verify that location yourself before accepting the report. Do
  not create a missing target file automatically — stop and align with the user.
- If the path is ambiguous, stop and ask the user instead of guessing.

## Context Summary

Maintain a short per-item summary before assignment (I3):

```text
item: {checkbox_id}
goal: {one sentence}
allowed_files: {paths}
existing_patterns: {paths or NOT FOUND}
contracts: {DTO/API/CLI/file formats or intentionally absent}
checks_to_run: {commands}
open_gaps: {none/list}
```
