# Route Detection — integrate-release

`integrate-release` поддерживает два маршрута: основной `spec` и короткий `small_fix`. Маршрут определяет, какие артефакты обязательны и как формировать CHANGELOG/merge message.

## Inputs

| Поле | Как получить |
|---|---|
| Branch | `git branch --show-current` |
| Spec slug | заменить `/` на `-` в branch |
| Spec path | `.ai/specs/{spec-slug}.md` |
| Fix statement | `.ai/fixes/{slug}.md`, где `{slug}` — ветка `fix/{slug}` без префикса |
| Worktree status | `git status --porcelain` |

## Decision Table

| Условие | Route | Действие |
|---|---|---|
| branch `main` или `master` | STOP | integrate-release запускается только с feature/fix ветки |
| spec path существует | `spec` | проверить все этапы реализации `✅` |
| spec path отсутствует и branch `fix/*` | `small_fix` | проверить принятый фикс: постановка `.ai/fixes/{slug}.md` доступна, коммит сделан после принятия, worktree clean |
| spec path отсутствует и branch не `fix/*` | STOP | обычной feature/bugfix ветке нужен spec |
| spec существует, но есть незавершённые этапы | STOP | вернуть пользователя к `implement-spec-stage` или `write-tests` |

## Spec Completion

Проверять только секцию `## Этапы реализации`. Не считать любые другие `###` заголовки этапами.

Этап завершён, если строка заголовка содержит `✅`.

## Small-Fix Acceptance

`scripts/detect_merge_route.py` подтверждает только сам маршрут и то, что spec не требуется; принятие фикса проверяется вручную:

- короткая постановка доступна в `.ai/fixes/{slug}.md` и содержит symptom/expected/scope/verification;
- фикс прошёл приёмку по хост-политике (исполнитель и приёмщик/основной агент), коммит сделан только после принятия — `git log {main}..HEAD --oneline` непустой;
- отдельный шаг write-tests для принятого короткого фикса не вводится;
- `git status --porcelain` пустой.

## Output

Перед продолжением зафиксировать:

```markdown
Merge route: `spec | small_fix`
Branch: `{branch}`
Spec: `{path | not required}`
Reason: `{why this route is valid}`
```
