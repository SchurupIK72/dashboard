# Merge Execution

Git-операции выполняются только после sufficiency gate.

## Evidence Record

Перед merge фиксируется итог проверки пригодности evidence: вердикт `scripts/validate_test_evidence.py` (`reuse`/`targeted`/`full`) с обоснованием и — при targeted rerun — supplement манифеста (`scripts/test_evidence.py supplement`). Дополненный манифест evidence стадируется вместе с CHANGELOG в том же docs-commit; вербальный GREEN без вердикта/supplement запись не заменяет. Для маршрута `small_fix` запись ссылается на согласованный defect+related scope.

## Order

Для `spec` route:

1. Stage `.ai/CHANGELOG.md`, updated version artifacts, archived spec и дополненный evidence-манифест (если менялся).
2. Commit: `docs: update CHANGELOG for {feature-name}`.
3. Checkout `main`.
4. Merge: `git merge --no-ff {branch} -m "feat: {feature-name} ({version})"` или `fix:` для bugfix.
5. Удалить merged branch только после успешного merge.

Для `small_fix` route:

1. Stage `.ai/CHANGELOG.md`, updated version artifacts (если они есть) и evidence-запись фикса.
2. Commit: `docs: update CHANGELOG for {summary}`.
3. Checkout `main`.
4. Merge: `git merge --no-ff {branch} -m "fix: {summary} ({version})"`.
5. Удалить merged branch только после успешного merge.

## Conflict Handling

Если возникает conflict:

- остановиться;
- не выполнять автоматический rollback;
- показать конфликтующие файлы;
- предложить пользователю отдельную сессию на resolution.

## Safety Notes

- Не использовать `git reset --hard`.
- Не удалять ветку до успешного merge.
- Не делать squash merge: workflow сохраняет merge commit.
- Не менять unrelated files ради чистоты истории.

## Post-merge Cleanup

Полная уборка ветки выполняется только после успешного merge через
`scripts/workflow_cleanup.py` — только файловые ресурсы `.ai/workflow-runs/`,
никаких процессов. Merge уже успешен: ошибка уборки видима, но не отменяет и
не ставит под сомнение выполненный merge.

1. Dry-run (по умолчанию) — план без изменений файловой системы:

   ```bash
   python scripts/workflow_cleanup.py --branch-slug {branch-slug} \
     --run-id {run-id} [--reference {final-manifest-or-report}]... [--orphans]
   ```

   - `--run-id` — идентификатор успешного запуска (его временный run-каталог);
     повторяется при нескольких запусках ветки.
   - `--reference` — итоговые manifests/reports (evidence-манифест ③,
     acceptance-отчёты, release-audit), чьи ссылки указывают внутрь удаляемых
     каталогов.
   - `--orphans` — явное перечисление кандидатов-сирот: нет branch/spec (включая
     archive), нет активного ownership/resume-заявки, terminal state (все пункты
     accepted и этап ✅) или пустой каталог; любое сомнение — сохранение.

2. Проверить план JSON: что удаляется, что сохранено и по какой причине
   (failed/active/неоднозначные runs сохраняются с точной причиной), куда
   переносится referenced evidence.

3. Применить ту же команду с `--apply`. Перед удалением referenced evidence
   копируется в долговечный `.ai/reports/evidence/...` и ссылки в итоговых
   документах переписываются — манифесты остаются разрешимыми.

4. Всегда неприкосновенны: `.ai/memory-candidates/`, backlog
   (`.ai/specs/draft/`), `.ai/reports/`, реестр `.ai/ownership/registry.json`,
   чужие runs. Отдельный layout plan-release и независимость worktrees
   учитываются самим скриптом.

5. Ненулевой exit или непустой `failures` — видимый отчёт пользователю в
   отчёте merge; merge НЕ откатывается и не объявляется несуществующим.
   Частичная неудача оставляет затронутый каталог неудалённым (per-path
   failure в плане).
