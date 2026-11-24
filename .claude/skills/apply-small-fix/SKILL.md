---
name: apply-small-fix
description: >
  Параллельная ветка workflow: небольшой фикс без ТЗ.
  Triggers: "небольшой фикс", "small fix", "quick fix", "мелкий фикс", "исправь быстро",
  "small-fix", "apply small fix", "примени фикс".
  Принимает короткую постановку из диалога (Default или Plan — режим не гейт),
  создаёт fix/* ветку, сохраняет постановку в .ai/fixes/<slug>.md, исполняет единый
  пункт fix-1 через общую систему ролей и приёмки, коммитит только после принятия.
type: workflow
step: F1
---

# Apply Small Fix Skill

**Параллельная ветка workflow** — небольшой фикс без создания ТЗ.

## Workflow Contract

```yaml
entry:
  branch: main | master
  condition:
    - короткая постановка из диалога: symptom / expected behavior / scope / verification
    - режим диалога (Default или Plan) не гейт — равнозначны
    - одна локальная обратимая исправляющая задача, не новые возможности
    - нет миграций, изменения публичных контрактов или перестройки архитектуры
    - .ai/specs/* не создаётся и не требуется
    - чужие правки в worktree сохраняются (не откатываются, не перезаписываются)

file_warning_threshold:
  source: policies.small_fix.file_warning_threshold (.ai/workflow.yaml, эффективное значение 3)
  semantics: warning, не запрет; превышение требует объяснения целостности задачи

statement:
  path: .ai/fixes/<slug>.md
  written_by: навык, до запуска пункта; исполнитель пункта файл только читает
  fields: symptom / expected behavior / scope / verification

execution:
  item: fix-1 — единственный пункт фикса
  package: контракт Fix-Route Packages (skills/implement-spec-stage/references/task-package.md): fix_path вместо spec_path
  roles: контракт Fix Items (skills/implement-spec-stage/references/agent-orchestration.md):
    zcode — workflow-implementer + ровно один workflow-acceptance-tester, принятие подтверждает основной агент;
    codex — один исполнитель, приёмка основным агентом лично;
    claude — существующая цепочка researcher → implementer → tester
  ownership: до запуска пункта — scripts/workflow_ownership.py reserve
    (--kind fix --scope fix-1 --branch fix/{slug} --run-id … --sources … --reports …);
    политика policies.ownership.enabled; CONFLICT → STOP с owner/run, без записи кода/тестов/статусов;
    resume сохраняет owner/evidence/счётчик; release после принятого коммита
  verification: references/verification.md — воспроизведение дефекта и прямо связанные проверки
  implementer_never_commits: true

escalation:
  trigger: объём задачи вырос — references/escalation-to-spec.md
  result: patch и доказательства сохранены, создан отдельный draft ТЗ, фикс не закрыт, ожидание согласования пользователя

exit:
  branch: fix/{slug}
  condition:
    - постановка сохранена в .ai/fixes/<slug>.md
    - пункт fix-1 принят по хост-политике (вердикт приёмщика и/или подтверждение основного агента)
    - проверка по references/verification.md выполнена или обоснованно не применима
    - unrelated changes не затронуты
  artifacts:
    - .ai/fixes/<slug>.md
    - изменённые файлы фикса
  commit: "fix: {summary}" — только после принятия пункта

next_skill: integrate-release

uses:
  - commit-helper
```

## Supporting Files

| Файл | Когда читать |
|---|---|
| `references/short-statement-gate.md` | Перед принятием задачи в `apply-small-fix` |
| `references/scope-classification.md` | При решении `apply-small-fix` или `plan-release` |
| `references/branching.md` | Перед созданием `fix/{slug}` |
| `references/minimal-patch.md` | Перед правкой файлов |
| `references/verification.md` | Перед выбором проверки фикса и при приёмке пункта |
| `references/escalation-to-spec.md` | Если объём задачи начал расти — остановка с сохранением patch и созданием draft ТЗ |
| `references/sufficiency-gate.md` | Перед commit и финальным отчётом |
| `assets/small-fix-plan-template.md` | Как шаблон короткой постановки |
| `assets/small-fix-report-template.md` | Как шаблон финального отчёта |
| `scripts/classify_small_fix.py` | Опционально: классифицировать описание/файлы |
| `scripts/validate_small_fix_entry.py` | Опционально: проверить входные условия |
| `scripts/validate_small_fix_scope.py` | Опционально: проверить patch scope |
| `scripts/validate_small_fix_completion.py` | Опционально: проверить итог перед `integrate-release` |

## Short Statement Gate

Использовать `references/short-statement-gate.md`.

Постановка собирается из диалога в любом режиме и должна содержать:

- симптом или дефект
- ожидаемое поведение
- границы изменения
- проверку готовности

Полная постановка из Default и из Plan равнозначна — не требовать переключения режима и не переспрашивать разрешение на уже ясное действие. Если постановка неполная — STOP и один предметный вопрос о пробеле (что именно неясно), а не формальный отказ.

Принятая постановка сохраняется в `.ai/fixes/<slug>.md` по шаблону `assets/small-fix-plan-template.md`: файл создаёт сам навык до запуска пункта, а исполнитель пункта его только читает — не создаёт и не редактирует.

## Границы небольшого фикса

Использовать `references/scope-classification.md`. Если задача сомнительная, проверить её через `scripts/classify_small_fix.py`.

`apply-small-fix` подходит, если изменение локальное, обратимо и проверяемо за одну сессию.

Число файлов — warning-порог `policies.small_fix.file_warning_threshold` (эффективное значение 3, из `.ai/workflow.yaml`), не запрет: превышение допустимо для единой целостной задачи с объяснением в отчёте, почему это всё ещё один небольшой фикс.

Если появляется хотя бы один признак ниже — STOP и направить в `plan-release` (независимо от числа файлов):

- требуется проектирование или выбор архитектуры
- нужно менять публичный API, схему данных, миграции или протоколы интеграций
- нужны новые возможности, а не исправление
- нужно несколько этапов реализации
- есть продуктовая неоднозначность, которую нельзя закрыть короткой постановкой

## Алгоритм

1. **Проверить короткую постановку** — собрать symptom/expected/scope/verification из диалога; при неполноте задать один предметный вопрос; использовать `references/short-statement-gate.md`.
2. **Подтвердить scope** — убедиться, что задача проходит границы небольшого фикса; превышение file-порога — объяснить целостность задачи; при явных признаках роста объёма перейти к шагу 7; использовать `references/scope-classification.md`.
3. **Создать ветку** — `fix/{slug}` от `main` или `master`; использовать `references/branching.md` и при необходимости `scripts/validate_small_fix_entry.py`.
4. **Сохранить постановку** — записать `.ai/fixes/<slug>.md` (четыре поля, шаблон `assets/small-fix-plan-template.md`) до запуска пункта; исполнитель пункта файл только читает.
5. **Запустить пункт fix-1** — сначала зарезервировать межсессионное владение тем же механизмом, что и `implement-spec-stage`: `python {repo_root}/scripts/workflow_ownership.py reserve --repo {repo_root} --kind fix --scope fix-1 --branch fix/{slug} --run-id {run-id} --owner {main-agent-session} --sources {области записи фикса} --reports {пути отчётов}`; `CONFLICT` → STOP с owner/run, без записи кода/тестов/статусов; счётчик rework — в ownership-записи, resume того же run его сохраняет. Затем собрать fix-пакет по контракту Fix-Route Packages (`skills/implement-spec-stage/references/task-package.md`): `fix_path` = `.ai/fixes/<slug>.md` вместо `spec_path`, единый пункт `fix-1`, оракул критериев — короткая постановка. Роли — по контракту Fix Items (`skills/implement-spec-stage/references/agent-orchestration.md`): zcode — `workflow-implementer` и ровно один `workflow-acceptance-tester`, принятие подтверждает основной агент; codex — один исполнитель, приёмка основным агентом лично; claude — существующая цепочка. Исполнитель пункта не коммитит.
6. **Проверить фикс** — по `references/verification.md`: воспроизведение дефекта и прямо связанные существующие проверки; существующий тест с buggy RED/fixed GREEN достаточен, нового теста не создавать; без защиты регрессионный тест пишет приёмщик; full suite автоматически не запускается; патч — минимальный, по `references/minimal-patch.md`, чужие правки сохраняются.
7. **Остановиться при росте объёма** — сработали триггеры `references/escalation-to-spec.md`: остановить зависимую реализацию, сохранить patch и доказательства, создать отдельный draft ТЗ с причиной эскалации, ждать согласования пользователя; фикс не закрыт, коммита нет, к шагу 8 не переходить.
8. **Коммит** — только после принятия пункта `fix-1`: вызвать `commit-helper` с сообщением `fix: {summary}`, затем освободить владение `scripts/workflow_ownership.py release --kind fix --scope fix-1 --run-id {run-id}` (штатное завершение); зависшее владение не снимается по mtime — только доказанное завершение или явное решение пользователя (`break --reason … --proof …`).
9. **Вывести** — пройти `references/sufficiency-gate.md`, при необходимости `scripts/validate_small_fix_scope.py` / `scripts/validate_small_fix_completion.py`, отчёт по `assets/small-fix-report-template.md`, указать `next_skill: integrate-release`.

## Continuous Improvement

По завершении каждого запуска выполни Improvement Triage:

1. Задача решена без неоднозначностей → вывести `no_change`.
2. Обнаружен повторно применимый урок → добавить краткую запись в `LEARNINGS.md`.
3. Инструкции навыка привели к ошибке → сначала создать eval-кейс в `EVALS.md`.
4. Предлагать патч `SKILL.md` только если та же проблема может повториться.
5. Предпочитать замену или удаление устаревшего guidance добавлению новых правил.
6. Не обновлять `SKILL.md` до прохождения соответствующего eval.
