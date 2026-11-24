# Agent Orchestration

Use this reference in I2, I4, and I5 when launching sub-agent roles. Sub-agents of
this skill run in waves: concurrency is allowed only inside a wave per
`references/parallel-scheduling.md`; dependent items are always sequential. The
short-fix route (`apply-small-fix`) launches its single fix item through the
same roles and adapters; see Fix Items below.

## Roles

Only the workflow roles participate in this skill, and the host policy fixed in I1
decides which ones: claude — researcher, implementer, acceptance tester; codex —
one implementer per item only (acceptance is the main agent's personal work, no
sub-agent); zcode — implementer plus exactly one independent acceptance tester per
item. Role definitions are the source of truth for input and output formats and
are not duplicated here:

- Product source: `templates/agents/workflow-researcher.md`,
  `templates/agents/workflow-implementer.md`,
  `templates/agents/workflow-acceptance-tester.md`
- Claude runtime: `.claude/agents/workflow-researcher.md`,
  `.claude/agents/workflow-implementer.md`,
  `.claude/agents/workflow-acceptance-tester.md`
- Codex runtime: `.codex/agents/workflow_researcher.toml`,
  `.codex/agents/workflow_implementer.toml`,
  `.codex/agents/workflow_acceptance_tester.toml`
- ZCode runtime: `.zcode/agents/workflow-implementer.md` and
  `.zcode/agents/workflow-acceptance-tester.md`, copied from `templates/zcode/`.


The write-tests roles (`workflow-test-curator`, `workflow-test-writer`,
`workflow-ui-scenarist`) are orchestrated by the `write-tests` skill, not here. The
legacy `code-mapper` and `data-flow-tracer` roles do not participate in this skill;
they remain available to other skills.

## Launch Rules

| Rule | Detail |
|---|---|
| One researcher per code item (claude) | Fresh launch with the item package; the researcher sees the repository as it is now, including changes accepted from previous waves |
| One implementer per item | claude: launched after the research reports of the whole wave are accepted (I3); codex/zcode: launched directly per wave once the package is composed — one self-sufficient implementer per item, docs/config included, performing its own research |
| One acceptance owner per item | claude: tester sub-agent launched immediately after the item's implementer returns (I5), it writes and runs acceptance tests — the functional verdict belongs to it; zcode: exactly one independent acceptor whose `passed` verdict still requires the main agent's confirmation; codex: no sub-agent — the main agent personally writes and runs the acceptance tests and decides |
| No nested delegation | An implementer never launches sub-agents of its own; item work is never routed through other roles (code-mapper, data-flow-tracer) to bypass the per-item topology |
| Waves, not free concurrency | Item agents run concurrently only inside a wave per `references/parallel-scheduling.md`; implementers never hold overlapping `allowed_files` |
| Package only | A sub-agent receives its task package, never the main chat history |
| Same role on rework | Rework returns go to the same role with the package plus written remarks; a failed acceptance suite returns to the implementer with the acceptance owner's failure list |

## Launching (adapters)

- Claude: Agent tool, sub-agent type `workflow-researcher` (model `haiku`); for the
  implementer — sub-agent type `workflow-implementer`, model per
  `references/model-selection.md` (alias slots `haiku`/`sonnet`/`opus` by
  complexity); for the tester — sub-agent type `workflow-acceptance-tester`
  (`haiku`, fixed for the role).
- Codex: select `workflow_implementer`, pinned to `gpt-6.1-sol` / `low`
  regardless of complexity. If named profiles are unavailable, pass that exact
  model/effort and the full role instructions explicitly with the isolated task
  package. This skill launches no researcher or tester on codex: the implementer
  researches itself and the main agent personally performs acceptance.
- ZCode: select the native `.zcode/agents/workflow-implementer.md` and exactly
  one `.zcode/agents/workflow-acceptance-tester.md`. Both pin
  `account:zai-individual-coding-plan/GLM-5.3` / `thoughtLevel: max`.
  The main agent confirms acceptance; no researcher is launched. If the host
  cannot select the native profile, explicitly supply the same model/settings
  and role instructions where supported; unavailable required model or isolation
  blocks the dependent item without fallback.

Parallel launches of one wave go out in a single batch (one message, several Agent
calls); their results are accepted individually, in the order they return.

If a required model is unavailable, or an isolated sub-agent context cannot be
created, stop per `references/model-selection.md`: blocking message naming the
model, run files kept, no silent fallback.

## Fix Items

A short-fix run (`apply-small-fix`, branch `fix/*`) launches exactly one item —
`fix-1` — through the same roles and adapters as a spec item; no separate
fix-specific roles exist:

- zcode: one `workflow-implementer` plus exactly one independent
  `workflow-acceptance-tester`; the acceptor's `passed` still requires the main
  agent's confirmation before the item closes.
- codex: one implementer only; the main agent personally performs acceptance —
  no tester sub-agent.
- claude: the existing researcher → implementer → tester chain keeps its
  topology when a fix runs under the claude policy.

No researcher is launched on codex/zcode for a fix item either: the implementer
researches the defect itself from the fix package, where `fix_path` replaces
`spec_path` (see `references/task-package.md`). Rework returns go to the same
implementer under the same shared counter. The implementer never commits — the
fix is committed by the main agent only after the item is accepted.

## Report Check

After a sub-agent returns, check the report against its role definition before
acceptance. The `### Result` block is the machine-readable contract: parse
`Item`/`Release` and `Verdict` first, then verify required sections are present, a
report over the token target is marked but never truncated — no character ceiling
applies, no placeholder phrases appear, and claimed files and commands match
reality. Verdict vocabularies are role-specific and fixed in the
role files (`implemented | blocked`, `passed | failed | blocked`). A report that
does not follow its format enters the acceptance loop of
`references/task-package.md` (concrete remarks, at most two rework returns).
