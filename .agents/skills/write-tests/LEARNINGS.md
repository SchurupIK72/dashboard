# Learnings — write-tests

Short reminders only; a lesson that exposes a failure mode first gets an eval case in `EVALS.md`, then a behavior fix.

- **On Windows a test process can hang in post-test teardown, not in the tests** — the summary line is already printed, but the process does not exit; this is not a hung test and never a reason to delete or weaken it. Kill the process tree, read the results from the output file.
- **Run test commands through a timeout wrapper with output to a file, never through a pipe** — a pipe waits for EOF from every process in the tree and hangs together with the stuck teardown; the wrapper budget is `defaults.budgets.checks.command_seconds`, and a process surviving past `defaults.budgets.checks.hang_seconds` is a hang: kill it, keep the log.
- **Set the encoding explicitly for wrapped test commands on Windows** (for example `PYTHONIOENCODING=utf-8`) — the legacy console code page corrupts pytest output written to a file.
- **A chunk killed without a summary line is a mid-run budget kill, not a hang** — check the output for failure/error dots: none means the budget ran out; re-run the chunk split in two and prove completeness by reconciling the executed node ids against the collected plan, not by re-running everything wide.
- **Prove a large suite by chunks, never by one over-budget run** — every chunk is a separate budget-wrapped command over explicit paths/node ids; the manifest reconciliation (sum of chunk records versus the collected set) is the completeness proof; a mismatch with equal totals still fails.
- **Trace coverage by behavior keyword across all of `tests/`, not by filename families** — a promoted or pre-existing test may already hold the behavior before a NOT_FOUND gap is declared.
