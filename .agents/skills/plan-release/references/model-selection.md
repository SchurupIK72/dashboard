# Model Selection

Use this reference after accepting a research report and before creating an
implementer, and when choosing the spec-reviewer model in `plan-release`.

## Complexity Table

Use the highest level identified; when unsure between two levels, take the higher
one. The number of files alone does not define the level.

| Purpose | Signs | Claude (alias slot) | Codex (`model` + `model_reasoning_effort`) | ZCode |
|---|---|---|---|---|
| Research | Locating edit sites, contracts, examples; context compression; no code changes | `haiku` | `gpt-6.1-sol` + `low` | session model |
| Simple implementation | Local edit by a verified pattern; no public contract changes; none of the risks below | `haiku` | `gpt-6.1-sol` + `low` | session model |
| Medium implementation | Coordinated changes to several components or new local logic with a clear solution; no complex-level signs | `sonnet` | `gpt-6.1-sol` + `low` | session model |
| Complex implementation | Contract changes, complex state/algorithms, concurrency, sensitive auth logic, migrations, data integrity | `opus` | `gpt-6.1-sol` + `low` | session model |
| Spec review | Completeness, consistency, verifiability, traceability, boundaries | `sonnet`; with complex-level signs — `opus` | `gpt-6.1-sol` + `low` | session model |

On Claude the researcher always gets the junior model, regardless of item
complexity. On Codex every purpose runs on the single supported profile
(`gpt-6.1-sol` + `low`) regardless of complexity; on ZCode the researcher runs
on the session model.

## Adapter Mapping

| Function | Claude (single role per function; model set at launch) | Codex (model fixed at `gpt-6.1-sol` + `low`) | ZCode |
|---|---|---|---|
| Researcher | `workflow-researcher` (`haiku`) | explicit `gpt-6.1-sol` + `low` launch with the researcher contract (named profile when one exists) | contract restated from `templates/agents/workflow-researcher.md` |
| Implementer | `workflow-implementer` with the model from the complexity table (`haiku` / `sonnet` / `opus`) | `workflow_implementer` — product source `templates/codex/workflow_implementer.toml` | pinned profile `templates/zcode/workflow-implementer.md` |
| Spec reviewer | `workflow-spec-reviewer` (`sonnet`; complex signs `opus`) | `workflow_spec_reviewer` (single profile; no complex variant) | contract restated from `templates/agents/workflow-spec-reviewer.md` |

Claude resolves the alias slots (`haiku`, `sonnet`, `opus`) through the user's
model settings; the product defaults for the slots ship in
`templates/settings.json.tpl` (installed as `.claude/settings.json`). The main
session model never changes automatically. Codex fixes the model and the
reasoning effort at `gpt-6.1-sol` + `low` in every launch: the product sources
of the role profiles live in `templates/codex/` with runtime copies under
`.codex/agents/`, and where no named profile exists the launch passes the
model, the effort, and the role text explicitly — never inheriting the main
agent's reasoning settings. ZCode pins the implementer profile in
`templates/zcode/workflow-implementer.md`: the model and `thoughtLevel: max`
are fixed in its frontmatter. The other workflow roles have no file-defined
ZCode profile: dispatch a general-purpose sub-agent with the role contract
restated from `templates/agents/{role}.md`; such a sub-agent follows the host
session model, so tier routing degrades to the session model — record the
deviation in the run state file when the complexity level demanded a higher
tier.

## Recording The Choice

Record one short line per launch, next to the accepted research:

```
{checkbox_id}: {simple|medium|complex} — {reason from the signs}; {model}/{effort}
```

Example (claude column): `complex — public contract change; opus/low`. On
codex the same line ends with `gpt-6.1-sol/low`; on zcode — with the session
model, or with the pinned implementer profile when that role is launched.

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
