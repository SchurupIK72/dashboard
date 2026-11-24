# Checklist Format

Use this reference in P4 when writing stage checklists, and later when the spec
must be extended during implementation. The checkbox format is a project
convention; the 85/100 scale is the active local quality tool, not an IEEE
normative threshold.

## Item Shape

A requirement is stated once — in the requirements table. A checklist item
contains an action and references, never a copy of the requirement wording:

```markdown
- [ ] C2.1 [R05, R06] Update the stage checklist template.
```

- `C{stage}.{n}` — stable item ID; `n` grows within the stage.
- `[R..]` — requirement IDs from the requirements table of this spec; every
  reference must exist.
- After acceptance only the mark changes: `- [x] C2.1 [R05, R06] …`.
- A mark is set only after acceptance (review of the result against the item
  criteria), never retroactively without review.

## Adding Necessary Work

Extra work inside the agreed requirements that is discovered during writing or
implementation becomes a NEW open item before it is performed:

```markdown
- [ ] C2.4 [R05] Add the requirement ID link — needed for verification tracing.
```

- Own unique ID; accepted IDs are never renumbered.
- One short phrase stating the reason, after `—`.
- It is never silently folded into an existing item or marked `[x]` on creation.

## Changing Requirements

If the change touches requirement wording, product behavior, architecture
decisions, or task boundaries, ask the user first. Until the answer, dependent
work is not performed. A scope extension arrives as a change to the requirements
table plus new checklist items — not as a quiet item rewrite.

## Not A Journal

The spec contains no session diaries, agent protocols, attempt lists, full test
output pastes, or duplicate "what was done" reports. Progress lives in checkbox
marks and stage statuses; the story of a run lives in its run directory, not in
the spec document.
