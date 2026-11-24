# Sufficiency Gate — apply-small-fix

Финальная проверка перед commit и передачей в `integrate-release`.

## PASS Criteria

| # | Критерий | Проверка |
|---|---|---|
| 1 | Branch | `fix/{slug}` |
| 2 | Statement | короткая постановка сохранена в `.ai/fixes/<slug>.md` |
| 3 | No spec | `.ai/specs/*` не создан для фикса; эскалационный draft — отдельный черновик ожидания согласования, не артефакт фикса (в этом случае см. «Эскалация вместо PASS») |
| 4 | Scope | файлы до warning-порога (по умолчанию 3, из `.ai/workflow.yaml`) или объяснение целостности задачи / механический характер превышения |
| 5 | Acceptance | пункт `fix-1` принят по хост-политике: вердикт приёмщика и/или подтверждение основного агента |
| 6 | Verification | проверка по `references/verification.md` выполнена (воспроизведение + прямо связанные) или обоснованно `not applicable` |
| 7 | Commit | `fix: {summary}` через `commit-helper` — только после принятия пункта |
| 8 | Next | указан `next_skill: integrate-release` |

## Эскалация вместо PASS

Если сработали триггеры `references/escalation-to-spec.md`, результат — не PASS, а «эскалация»: patch и доказательства сохранены, отдельный draft ТЗ создан, фикс не закрыт (коммита нет, готовность не объявлена), ожидается согласование пользователя.

## FAIL Signals

- diff содержит migration/schema/API change;
- commit сделан до принятия пункта `fix-1`;
- фикс объявлен готовым без вердикта приёмки;
- при эскалации patch или draft не сохранены, либо работа продолжена молча;
- появились новые workflow/spec artifacts, не являющиеся эскалационным draft;
- есть unrelated changes в staged files;
- проверка не выполнена и не обоснована как `not applicable`.

## Output

```markdown
Small-fix gate: PASS
Branch: `fix/{slug}`
Statement: `.ai/fixes/{slug}.md`
Item: `fix-1`
Acceptance: {вердикт приёмщика / подтверждение основного агента}
Files: {N}
Verification: `{command/result}`
Commit: `fix: {summary}` — после принятия
Next: `integrate-release`
```
