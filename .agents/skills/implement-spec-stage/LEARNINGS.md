# Learnings — implement-spec-stage

Only fundamental lessons; git keeps provenance.

## Spec and DoD

- Sufficiency gate: CHAIN_BREAK at an API boundary → clarify BEFORE implementing; spec is a proposal, DoD is the gate (quantifiers → grep all; env vars override file config).
- A package's example file name («например X.md») is a suggestion, not a required path: an accumulated no-new-files pin can make a section of an existing reference the right carrier — amend the package and have the acceptor judge content/wiring, not the file name.
- An integration item whose file links the siblings' outputs runs LAST: consumed-contract edges override record-order priority; the linking file is accepted only after every reference it cites exists.
- Acceptance oracles are contracts: PASS/FAIL baselines before launch (fix the example, not the check); RED-first needs BOTH (buggy RED + fixed GREEN); diff-vs-HEAD expires at commit → presence/monotonicity guards; ""/number options → real-module harness; a live fixture mutated by a later item — synthesize from pins.
- Added/removed surface stales a hidden PIN FAMILY (len/count/manifest/shape) — grep the literal AND its family at wave planning; census/registry pins are EXACT equalities; later waves' edits stale exact-set scope pins — that wave's acceptor extends the accumulated set.
- «Reuse via import» can invert a layer boundary: shared logic lives in the owning module; CLI/rehearsal/tests import it.
- Shared-contract wave items: implementers in record order, generated-contract regeneration last; judge items by their own hunks (diff stats mix waves).
- Spec-ref pollution (concrete spec-marker IDs leaking into file content): grep the accumulated diff incl. untracked; checkbox pairs render DOUBLED — verify via grep -F; I5 also greps the tester's NEW file and runs the formatter check — `passed` is functional only, trace/format drift are test defects.
- Researcher limits: a related-tests LIST is not an adaptation prediction — grep CONCRETE symbols; set import-ban guards BEFORE assigning an implementer.
- Spec edited mid-run: re-read before each checkbox edit; the executing skill runs by its loaded revision — update the source and the runtime copies; unauthored dirty-tree edits become the item baseline.
- Acceptance must DEMONSTRATE the behavior: synthesize representative records; empty states prove nothing.
- Grep the FULL pin family at I1, not just role/target literals: exact count/len pins (template counts, target sets) and no-new-files bans in EARLY-stage test files stale on any surface growth — five surfaced late in one stage; reserve them with the wave plan. workflow_ownership.py cannot extend an active claim's scopes (reserve self-conflicts, release marks completed) — late scopes go to state scope_amendments + disclosure; a scope-extension command is a backlog item.
- The no-comments gate covers TEST files too: a `#` justification inside a pin adaptation is a violation — rationale lives in the acceptance report, never inline in the test.

## Tests and EXIT

- Chunked runs: reconcile vs --collect-only; EXIT=124 + summary = teardown hang; I6 chunks SEQUENTIALLY (parallel pytest → phantom failures); a stage-local set over 150 s → filename chunks from the item→tests mapping (never widen).
- Wave-close skips integration: grep removed ids/selectors incl. unit pins; run integration explicitly when it matters.
- Pre-existing red on tests the stage did not write: prove ownership on a clean HEAD checkout — route to the owning stage.
- A closed stage's skips may test an ABOLISHED contract — classify, don't lift literally; a pytest.ini overrides addopts.
- I6 sweeps ALL stage files: reconcile `git status` vs allowed_files; a ③ reopen leaves renames staged → `git restore --staged`.
- Run-state files must be JSON-serializable (datetimes as ISO strings); flip items[].status together with accepted_items — downstream tools (cleanup terminality) read items[].status, not lists, and require state["stage_status"]="✅".
- A legitimate contract shift stales pins in test files OUTSIDE the item's reserved test scope (cross-stage snapshot/meta pins): grep the literal's pin family repo-wide at wave planning and reserve the affected files, else the final-matrix item finds them late — route stale pins to the owning acceptor via package amendment, product residue (e.g. a manual mirror like .claude/rules/) to the owning implementer.
- Windows: pytest tmp inside the run dir (--basetemp) leaves undeletable empty skeletons — point basetemp at system temp; empty residue is harmless, full branch cleanup stays with integrate-release.
- item_baseline: hash ALL allowed files at capture — cross-wave attribution diffs baseline hashes, no worktree reconstruction.
- item_diff for later waves on an uncommitted multi-wave tree mixes earlier waves' hunks in shared files — either generate it baseline-relative or hand the acceptor the baseline hashes for attribution; acceptors otherwise reconstruct footprints by hand.
- Pure-test items (pins/test refresh): the implementer is forbidden `tests/`, the main agent likewise — the acceptance-tester role executes them with its own acceptance package; the verdict is the permanent contract.
- Parallel wave items running repo-wide sync validators see a sibling's mid-flight mirror drift: filter findings to the item's own area; the stage-level sync re-check happens at I6 after all mirrors land.

## dot_ai port specifics

- Dispatching roles via general-purpose sub-agents: restate the contract constraints in the dispatch prompt itself (exact section headings, char budget, no forbidden phrases, forward-slash paths) — validate with `scripts/validate_agent_output.py`, budgeting one correct-and-revalidate cycle.
- Write the research package to a FILE before launching the researcher (launch prompt = summary + link); without the file the sub-agent recovers via INSUFFICIENT_CONTEXT.
- When porting LEARNINGS/EVALS, check the per-file token budgets via `scripts/validate_skill_memory.py` — advisory limits resolved from `.ai/workflow.yaml`; character caps are not memory limits.
- A new render-source role template must extend the install contract (`init/references/host-install.md`) AND the install-test fixture lists (`RENDER_SOURCES`/`RENDERED_RUNTIME_COPIES`/`RENDER_MANAGED_BASENAMES`) in the same item — byte-copying a placeholder template fails install verification; found at the v0.14.0 merge (impact-reporter).
- A stage that ports a skill into `skills/` syncs the `.agents/skills/` and `.claude/skills/` mirrors in the same stage; host-profile copies (`.claude/agents/` from `templates/agents/`) sync manually too — the hash validator covers skills/ only; the full-tree re-sync stays with the final stage.
