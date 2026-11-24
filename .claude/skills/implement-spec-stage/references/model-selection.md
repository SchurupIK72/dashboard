# Model Selection

Use this reference in I3 — after accepting a research report (claude) or after
composing the item packages (codex/zcode) — and when choosing the spec-reviewer
model in `plan-release`.

## Complexity Table

Use the highest level identified; when unsure between two levels, take the higher
one. The number of files alone does not define the level.

| Purpose | Signs | Claude (alias slot) | Codex (`model` + `model_reasoning_effort`) | ZCode |
|---|---|---|---|---|
| Research | Locating edit sites, contracts, examples; context compression; no code changes | `haiku` | `gpt-6.1-sol` + `low` | session model |
| Simple implementation | Local edit by a verified pattern; no public contract changes; none of the risks below | `haiku` | `gpt-6.1-sol` + `low` | native GLM-5.3 / max |
| Medium implementation | Coordinated changes to several components or new local logic with a clear solution; no complex-level signs | `sonnet` | `gpt-6.1-sol` + `low` | native GLM-5.3 / max |
| Complex implementation | Contract changes, complex state/algorithms, concurrency, sensitive auth logic, migrations, data integrity | `opus` | `gpt-6.1-sol` + `low` | native GLM-5.3 / max |
| Acceptance testing | Writing and running acceptance tests for one implemented item | `haiku` | `gpt-6.1-sol` + `low` | native GLM-5.3 / max |
| Spec review | Completeness, consistency, verifiability, traceability, boundaries | `sonnet`; with complex-level signs — `opus` | `gpt-6.1-sol` + `low` | session model |

Research launches in this skill happen only under the claude policy: codex/zcode
launch no researcher — research is part of the implementer's work — so the
Research row applies to claude (and to the planning researcher of `plan-release`).
On claude the researcher always gets the junior model, regardless of item
complexity, and the acceptance tester also always gets the junior model — the
tier of the implementer never raises the tester. On zcode the acceptor uses its native pinned GLM-5.3/max profile. On codex there is no
researcher and no tester sub-agent: acceptance tests are written and run by the
main agent personally.

## Adapter Mapping

| Level | Claude (single role per function; model set at launch) | Codex (model fixed in the role file) | ZCode (native item profiles) |
|---|---|---|---|
| Researcher (claude policy only in this skill) | `workflow-researcher` (`haiku`) | not launched | not launched |
| Implementer simple | `workflow-implementer` launched with `model: haiku` | `workflow_implementer` | `.zcode/agents/workflow-implementer.md` |
| Implementer medium | `workflow-implementer` (`sonnet`, default) | `workflow_implementer` | `.zcode/agents/workflow-implementer.md` |
| Implementer complex | `workflow-implementer` (`opus`) | `workflow_implementer` | `.zcode/agents/workflow-implementer.md` |
| Acceptance tester | `workflow-acceptance-tester` (`haiku`, fixed for the role) | not launched (main agent accepts) | `.zcode/agents/workflow-acceptance-tester.md` |
| Spec reviewer | `workflow-spec-reviewer` (`sonnet`; complex signs `opus`) | `workflow_spec_reviewer` | `templates/agents/workflow-spec-reviewer.md` |

Claude resolves the alias slots (`haiku`, `sonnet`, `opus`) through the user's
model settings; the product defaults ship in `templates/settings.json.tpl`.
The main session model never changes automatically. Codex uses the unified
`.codex/agents/workflow_implementer.toml` at `gpt-6.1-sol` / `low` for every
item complexity; complexity remains a rationale, not a profile selector. All
Codex workflow roles, including the separate planning P2 researcher and release
roles, use this supported model/effort pair. When the host cannot select a named
profile, pass the model, effort and role instructions explicitly with the isolated
package; never inherit the main model. Retired complexity profiles are not active
alternatives. ZCode discovers `.zcode/agents/workflow-implementer.md` and
`.zcode/agents/workflow-acceptance-tester.md`, both pinned to
`account:zai-individual-coding-plan/GLM-5.3` and `thoughtLevel: max`.
Other ZCode task-specific roles use their contract and session model.

## Recording The Choice

Record one short line per launch, next to the accepted research (claude) or the
composed item package (codex/zcode):

```
{checkbox_id}: {simple|medium|complex} — {reason from the signs}; {model}/{effort}
```

Example (Codex): `item-1: complex — public contract change; gpt-6.1-sol/low`.

An explicit user model assignment overrides the table, is followed as given, and is
recorded the same way with the `user override` marker. The table never justifies
raising the model after review remarks without asking the user.

## Unavailability Is A Stop

If the chosen model is unavailable, or an isolated sub-agent context cannot be
created:

1. Stop the dependent item with an explicit blocking message naming the model and
   the reason.
2. Keep the run files (see `references/run-artifacts.md`) — nothing is cleaned up.
3. No silent fallback to another model and no passing the full chat history instead
   of a package.

Resuming requires an explicit user decision (retry later, another model by user
choice, or doing the item in the main session as a non-code/document action).
