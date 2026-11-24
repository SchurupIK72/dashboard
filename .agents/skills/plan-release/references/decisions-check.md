# Decisions Check

Use this reference during step 5 of the plan-release algorithm ("Study project context") to verify draft requirements against formalized product boundaries.

## Format of `.ai/DECISIONS.md`

```markdown
# Project Decisions — {Project Name}

Product boundaries: чем проект является, а чем нет.

## IS (проект является)

- {statement about what the project does/includes}

## IS NOT (проект не является)

- {statement about what the project does not do/excludes}
```

Each entry is a single statement about a product boundary. Technical decisions live in ADR (`docs/decisions/`) or inside specs, not here.

## Check Algorithm

Run this algorithm after gathering draft requirements and before writing the spec.

### Step 1: Read decisions

If `.ai/DECISIONS.md` exists, read all IS and IS NOT entries. If it does not exist, skip the check and add a note to the spec: "Product boundaries are not formalized" in `Архитектурные решения`.

### Step 2: Check each draft requirement against IS NOT

For each draft requirement in the spec:

1. Compare the requirement's implied scope against every IS NOT entry.
2. If the requirement directly contradicts an IS NOT boundary → this is a **conflict**.
3. If the requirement is adjacent but not clearly contradicting → this is an **ambiguity**.

### Step 3: Check each draft requirement against IS

For each draft requirement:

1. Compare the requirement's implied scope against every IS entry.
2. If the requirement introduces a new scope area not covered by any IS entry → this is an **expansion**.
3. If the requirement clearly falls within an existing IS entry → no action needed: the spec cites that IS entry as the decision's source instead of re-asking the user (`policies.interview.repeat_confirmed_general` in `.ai/workflow.yaml`).

### Step 4: Handle conflicts

For each conflict found in Step 2:

1. Stop and raise an AUQ question asking the user whether the IS NOT boundary should be expanded.
2. Do not finally accept the spec on this point until the user resolves the conflict: while the question is open, only independent research and a draft carrying the conflict as an explicit assumption are allowed (`policies.interview.unanswered` in `.ai/workflow.yaml`); dependent changes wait, and a `default` mark is not consent.
3. If the user confirms expansion → mark for "Расширение решений проекта" section.

### Step 5: Handle expansions

For each expansion found in Step 3:

1. Record the new boundary in the spec's "Расширение решений проекта" table.
2. Raise an AUQ question to confirm the expansion is intentional.
3. If the user confirms → include in the spec; if not → remove the expanding requirement.
4. Record a confirmed expansion once: product boundaries in `.ai/DECISIONS.md`, settings values in the permanent `.ai/workflow.yaml`; do not copy the same values into a second active source.

## AUQ Question Templates

### Conflict with IS NOT

```markdown
Need to clarify scope before writing the spec:

The requirement "{requirement}" conflicts with a product boundary: "{IS NOT entry}".

Should the product boundary be expanded for this spec?

Why it matters: expanding an IS NOT boundary changes the product scope and will affect future specs.
```

### New scope not covered by IS

```markdown
Need to clarify scope before writing the spec:

The requirement "{requirement}" introduces a new area not described in product boundaries: "{new area}".

Add it as a new IS boundary?

Why it matters: recording the expansion makes it explicit and visible for future specs.
Suggested default: add to the «Расширение решений проекта» section with an IS mark
```

## Output

After running the algorithm, the spec should contain:

- Conflicts resolved through AUQ (recorded in `Архитектурные решения`); reused boundaries cited by their source entry.
- Expansions documented in «Расширение решений проекта» table (if any).
- A note about missing DECISIONS.md (if it does not exist).
