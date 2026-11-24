# I3. Assignment

Load this file right before performing I3 — on claude after the research reports
of the wave are accepted; on codex/zcode after the item packages of the wave are
composed in I2. The main agent chooses the implementer model and completes the
implementer package for every item of the wave (codex/zcode: every item, docs and
configuration included); implementers launch only after all packages are ready
(I4).

## Inputs

- claude: accepted research reports of the wave's items
- Item requirements, boundaries, and allowed files per item
- Relevant user decisions, including any explicit model assignment

## Checklist

- [ ] For every item of the wave: classify the complexity per
  `references/model-selection.md` — use the highest identified level; when unsure
  between two levels, take the higher.
- [ ] Record one choice line per item next to its accepted research (claude) or
  its composed package (codex/zcode):
  `{checkbox_id}: {simple|medium|complex} — {reason from the signs}; {model}/{effort}`.
- [ ] An explicit user model assignment overrides the table; follow it as given and
  record it with the `user override` marker.
- [ ] Compose one implementer package per item (`references/task-package.md`).
  claude: all package fields plus `research_report` — the accepted researcher
  output for that exact item. codex/zcode: the package contract fields only,
  without `research_report` — the implementer performs its own research; the
  package is complete only with `item_baseline` recorded. Store them in the run
  directory.
- [ ] Confirm the chosen models and roles are actually available in this
  environment before the parallel launch.

## Result

Recorded model choices with rationale, and a complete implementer package for every
item of the wave (allowed files, constraints; claude: research report included).

## Transition

- Proceed to I4 (launch the implementers of the wave in one parallel batch).
- Model unavailable, or an isolated context is impossible → STOP with a blocking
  message naming the model (`references/model-selection.md`); run files are
  kept; no silent fallback.
