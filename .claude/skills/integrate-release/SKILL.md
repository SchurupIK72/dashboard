---
name: integrate-release
description: >
  Шаг ④ workflow: интеграция релиза — merge в main с обновлением CHANGELOG.
  Triggers: "merge в main", "мерж", "готово к релизу", "merge-helper",
  "integrate release", "интегрируй релиз".
  Проверяет качество, обновляет CHANGELOG, архивирует spec для spec-маршрута
  или пропускает архивирование для apply-small-fix, выполняет merge.
type: workflow
step: 4
---

# Integrate Release Skill

**Шаг ④ workflow** — интеграция релиза: финальный merge в main с обновлением документации.

## Workflow Contract

```yaml
entry:
  branch: NOT main | master
  routes:
    spec:
      artifacts:
        - .ai/specs/{branch-name}.md
      condition:
        - все этапы ✅
    small_fix:
      branch_pattern: fix/*
      artifacts:
        - .ai/fixes/{slug}.md
      condition:
        - ветка создана навыком apply-small-fix
        - короткая постановка доступна в .ai/fixes/{slug}.md (symptom/expected/scope/verification)
        - фикс принят по хост-политике и закоммичен только после принятия
        - .ai/specs/{branch-name}.md отсутствует и не требуется
  condition:
    - нет uncommitted changes

exit:
  branch: main
  artifacts:
    - .ai/CHANGELOG.md
    - .ai/release-notes/{version}.md
    - version artifacts updated to release version
    - .ai/specs/archive/{branch-name}.md  # только spec-маршрут

next_skill: deploy-release

uses:
  - commit-helper
```

## Repo-root Scripts

| Скрипт | Когда запускать | Назначение |
|---|---|---|
| `scripts/validate_workflow_state.py` | В Шаге 0 (workflow state gate) | Общий workflow state gate (`--step integrate-release`). Путь **от корня репозитория**, не от директории навыка. |
| `scripts/check_tokenizer_updates.py` | В Шаге 1.5 (ENTRY-preflight до снимка параметров) и Шаге 8c (повтор после снимка перед merge) | Read-only проверка актуальности tiktoken по официальным PyPI/GitHub; отчёт пишется в `.ai/reports/dependencies/tiktoken-<version>.md`. Путь **от корня репозитория**. |
| `scripts/audit_skill_memory.py` | В Шаге 8b (memory audit перед merge) | Diff/count/hash-отчёт памяти навыков относительно `main`; результаты advisory. Путь **от корня репозитория**. |
| `scripts/find_trace_refs.py` | В Шаге 6.5 (регистрация разрешённых D-ссылок до аудита) и как helper release-аудитора в Шаге 8d | Проверка устойчивых ссылок на решения (`D##` → реестр, по умолчанию `.ai/DECISIONS.md`) в release diff/файлах; мёртвая ссылка — FAIL с file:line; `--registry`/`--root` принимают реестр установленного проекта. Путь **от корня репозитория**. |
| `scripts/validate_test_evidence.py` | В Шаге 2 (пригодность evidence) и повторно в Шаге 9 перед merge | Сопоставление evidence-манифеста ③/принятого F① с prospective merge-state (diff основной ветки + собственные version/audit/config изменения): вердикты `reuse` / `targeted` (с перечнем наборов и supplement манифеста) / `full`. Путь **от корня репозитория**. |
| `scripts/workflow_cleanup.py` | В Шаге 9.5 (полная уборка ветки после успешного merge) | Dry-run по умолчанию + `--apply`: удаляет только идентифицированные временные ресурсы текущей ветки/запуска (`--run-id`), переносит referenced evidence (`--reference`) в долговечный `.ai/reports/evidence/` с обновлением ссылок, сохраняет failed/active/неоднозначные runs, memory-candidates, backlog, отчёты и чужие runs; `--orphans` — явный перечень кандидатов-сирот. Ошибка видима и не отменяет успешный merge. Путь **от корня репозитория**. |

## Skill-local Supporting Files

| Файл | Когда читать |
|---|---|
| `references/route-detection.md` | При выборе маршрута `spec` или `small_fix` |
| `references/pre-merge-checks.md` | Перед запуском финальных проверок |
| `references/memory-audit.md` | В Шаге 8b, перед формированием отчёта аудита памяти |
| `references/cleanliness-audit.md` | В Шаге 8d, перед вызовом release-аудитора (task-пакет, зоны, вердикты) |
| `references/module-size-review.md` | При проверке лимита 500 строк |
| `references/changelog-entry.md` | Перед обновлением `.ai/CHANGELOG.md` |
| `references/release-notes-entry.md` | Перед созданием `.ai/release-notes/{version}.md` |
| `references/version-sync.md` | Перед архивированием и merge |
| `references/spec-archiving.md` | Перед переносом spec в `archive/` |
| `references/merge-execution.md` | Перед git-операциями merge |
| `references/sufficiency-gate.md` | Перед финальным commit/merge |
| `assets/changelog-entry-template.md` | Как шаблон записи CHANGELOG |
| `assets/release-notes-template.md` | Как шаблон пользовательских release notes |
| `assets/merge-report-template.md` | Как шаблон финального отчёта |
| `scripts/detect_merge_route.py` | Опционально: определить маршрут и spec path |
| `scripts/validate_pre_merge.py` | Опционально: проверить entry conditions |
| `scripts/find_large_modules.py` | Опционально: найти модули >500 строк |
| `scripts/validate_changelog_entry.py` | Опционально: проверить новую запись CHANGELOG |
| `scripts/validate_merge_completion.py` | Опционально: проверить post-merge состояние |

## Алгоритм

### Шаг 0: Workflow state gate

Запустить `python {repo_root}/scripts/validate_workflow_state.py --step integrate-release` (путь от корня репозитория, не от директории навыка); если exit code ≠ 0 — вывести issues/warnings и STOP.

### Шаг 1: Определить маршрут

Использовать `references/route-detection.md`. Если маршрут неочевиден, запустить `scripts/detect_merge_route.py`.

```bash
branch=$(git branch --show-current)
spec_slug=$(echo "$branch" | tr '/' '-')
spec_file=".ai/specs/${spec_slug}.md"
fix_slug=$(echo "$branch" | sed 's|^fix/||')
fix_file=".ai/fixes/${fix_slug}.md"
```

Если `spec_file` существует → маршрут `spec`: проверить, что все этапы ✅.

Если `spec_file` отсутствует и ветка соответствует `fix/*` → маршрут `small_fix`: убедиться, что короткая постановка доступна в `.ai/fixes/{slug}.md` (`{slug}` — слаг ветки `fix/{slug}`) и содержит symptom/expected/scope/verification, фикс принят по хост-политике (исполнитель и приёмщик/основной агент — как требует хост) и закоммичен только после принятия, а uncommitted changes отсутствуют. Наличие commit в ветке проверяется через `git log {main}..HEAD --oneline`. Отдельный шаг write-tests для принятого короткого фикса не вводится.

Иначе STOP: для обычной фичи/багфикса нужен spec, а no-spec merge разрешён только после `apply-small-fix`.

### Шаг 1.5: ENTRY-preflight актуальности tiktoken (до снимка параметров)

Запустить read-only preflight из корня репозитория ДО фиксации снимка параметров запуска (снимок фиксируется аудитом в Шаге 8b):

```bash
python scripts/check_tokenizer_updates.py --report-dir .ai/reports/dependencies
```

Отчёт пишется в `.ai/reports/dependencies/tiktoken-<pinned>.md` (дата, источники, latest/закреплённая/установленная версии, результат). Вердикт читается из JSON в stdout; exit code 2 кодирует статусы UNKNOWN/INCOMPATIBLE, а не провал шага. Действия по вердикту:

| Статус | Действие до снимка |
|---|---|
| `CURRENT` | Закреплённая версия актуальна; продолжать без изменений |
| `UPDATE_AVAILABLE` | Совместимая новая stable: по постоянному поручению пользователя обновить ТОЛЬКО tiktoken — (1) снять golden-значения подсчёта на текущей версии; (2) закрепить точную новую версию в `.ai/workflow.yaml` (`tokenizer.version`) и lock-артефактах; (3) выполнить `python scripts/prepare_tokenizer.py`; (4) offline-проверка таблиц и совместимости Python; (5) пересчитать память/отчёты — смена метрики означает новый baseline без правки истории; (6) только после зелёных проверок фиксируется снимок (Шаг 8b идёт на новом pin). Encoding и бюджеты автоматически не меняются. Красная проверка останавливает именно обновление: pin возвращается к прежней версии, запуск пересчитывается на ней, вопрос выносится пользователю |
| `INCOMPATIBLE` | Обновление остановлено до решения пользователя; запуск остаётся на прежнем pin и продолжается; актуальность не заявляется |
| `UNKNOWN` | Официальный источник недоступен или расходится: версия не называется последней; не блокирует ни memory-аудит, ни merge; UNKNOWN фиксируется в отчёте |

prerelease/dev/yanked исключаются самой проверкой. Блокирующей является только невозможность выполнить сам preflight (нет скрипта или конфигурации), а не его вердикт.

### Шаг 2: Pre-commit checks

Использовать `references/pre-merge-checks.md`. Если нужно, запустить `scripts/validate_pre_merge.py`.

Вместо неизменного полного повтора всего набора сопоставить доказательство GREEN шага ③ (либо принятого F①) с prospective merge-state:

```bash
python scripts/validate_test_evidence.py --manifest {evidence-manifest} [--route spec|small_fix] [--defect-scope {scope.json}] [--impact-map {map.json}]
```

`{evidence-manifest}` — манифест шага ③ по контракту навыка write-tests (branch/base/tested commit, хеши проверенных файлов/config/lock, exact commands, node IDs, результаты) либо evidence принятого короткого фикса. Вердикт и exit code:

| Вердикт | Exit | Действие |
|---|---|---|
| `reuse` | 0 | Совпавшая проверяемая область и неизменённые selection/dependencies: повтор не нужен; зафиксировать вердикт и обоснование в отчёте merge |
| `targeted` | 1 | Выполнить только перечисленные `required_sets`/`required_checks` (бюджеты — только через `scripts/workflow_config.py`; suites/чанки учитываются при выборе наборов); каждая команда — timeout-обёртка ≤ `command_seconds`, вывод в файл, без pipe; результат записать дополнением манифеста: `python scripts/test_evidence.py supplement --manifest {evidence-manifest} --supplement {supplement}` (supplement сформирован валидатором; после rerun дополнить его `records`) |
| `full` | 2 | Запустить полный соответствующий suite с теми же budget-правилами; для маршрута `small_fix` полный набор не навязывается только из-за отсутствия ③ — достаточно согласованного defect+related scope (`--defect-scope`) |

Правила:

- Вердикт вычисляется по ревизии/хешам/node IDs манифеста; непустой tests diff и emoji-статусы не являются условием или доказательством.
- Собственные изменения integrate-release (CHANGELOG, release notes, version artifacts, отчёты аудитов) входят в prospective merge-state: перед merge повторить проверку (Шаг 9); release-артефакты rerun не требуют, изменённый `.ai/workflow.yaml`/lock даёт `full` — старое доказательство не прикрывает новую конфигурацию.
- Отсутствующий/устаревший/непокрытый evidence требует недостающего набора; при невозможности доказать границы — полный соответствующий suite. Для F① достаточно согласованного defect+related scope (воспроизведение дефекта + прямо связанные проверки).

### Шаг 3: Проверка лимита размера модулей (500 строк)

Использовать `references/module-size-review.md`. Если нужно, запустить `scripts/find_large_modules.py`.

Найти все `.py` файлы, превышающие 500 строк:

```bash
find src/dashboard/ -name "*.py" -exec awk 'END { if (NR > 500) print FILENAME ": " NR " lines" }' {} \;
```

Для каждого найденного файла:

1. **Проверить наличие пометки** `MODULE_SIZE_REVIEWED` в начале файла
2. **Предложить пользователю решение:**
   - **Вариант A: Рефакторинг** — разбить модуль
   - **Вариант B: Оставить** — если рефакторинг нецелесообразен
3. **Если принято решение оставить** — добавить:
   ```python
   # MODULE_SIZE_REVIEWED: {date}. Решение: оставить. Причина: {одна строка}
   ```

### Шаг 4: Обновление CHANGELOG

Использовать `references/changelog-entry.md` и `assets/changelog-entry-template.md`. После правки можно запустить `scripts/validate_changelog_entry.py`.

Добавить запись в `.ai/CHANGELOG.md`.

Для `spec` использовать тип `Added / Fixed / Changed` по содержанию spec:

```markdown
## [{version}] — {date}

### Added / Fixed / Changed — {Feature Name}

Краткое описание изменений.

**Компоненты:**
- [module/](path/): описание

**Tests:** {X} passed
```

Для `small_fix` использовать patch bump и тип `Fixed`:

```markdown
## [{version}] — {date}

### Fixed — {Small Fix Summary}

Краткое описание исправления без ссылки на spec.

**Tests:** {X} passed
```

### Шаг 4.5: Составление release notes для пользователей

Использовать `references/release-notes-entry.md` и `assets/release-notes-template.md`.

Создать файл `.ai/release-notes/{version}.md` — пользовательское описание изменений релиза. Это то, что увидят конечные пользователи продукта при обновлении версии.

Отличия от CHANGELOG (Шаг 4):

- **CHANGELOG** — технический документ для разработчиков: компоненты, точные пути модулей, tests passed.
- **release notes** — пользовательский документ: что нового, что исправлено, как это меняет повседневную работу, известные ограничения.

Источники контента:

1. Spec — польза фичи для пользователя, мотивация.
2. CHANGELOG entry (Шаг 4) — точные правки для точности формулировок.
3. `git log {main}..HEAD` — дополнительные детали, не попавшие в spec/CHANGELOG.

Стиль — развёрнутый русский с emoji-заголовками: `🆕 Что нового`, `🔧 Что исправлено`, `⚠️ Заметки`, `📌 Ограничения`. Без технических деталей: модулей, путей, `**Компоненты:**`, `**Tests:**`.

Для маршрута `small_fix` — упрощённый шаблон: только `# v{version} — {date}` + краткое summary + секция `🔧 Что исправлено`.

Если в репозитории уже есть `.ai/release-notes/{version}.md` — перезаписать, конфликтов быть не должно (один релиз = одна версия).

### Шаг 5: Синхронизация версии

Использовать `references/version-sync.md`.

Проверить, что версия релиза из ветки/spec совпадает с записью CHANGELOG. Обновить все файлы, где проект явно трекает актуальную версию: `pyproject.toml`, `package.json`, `Cargo.toml`, `VERSION`, `version.txt`, исходники с `__version__` и проектные аналоги.

Если найден version artifact, который не обновлён до версии релиза, STOP до исправления.

### Шаг 6: Обновление DECISIONS.md

Только для маршрута `spec`:

Если spec содержит секцию «Расширение решений проекта» с новыми IS/IS NOT записями — извлечь их и добавить в `.ai/DECISIONS.md`:

1. Прочитать spec и найти секцию «Расширение решений проекта».
2. Для каждой записи с типом `IS` — добавить строку в секцию `## IS` файла `.ai/DECISIONS.md`.
3. Для каждой записи с типом `IS NOT` — добавить строку в секцию `## IS NOT` файла `.ai/DECISIONS.md`.
4. Если `.ai/DECISIONS.md` не существует — создать по шаблону `templates/DECISIONS.md.tpl`.

Если секция «Расширение решений проекта» отсутствует — пропустить этот шаг.

### Шаг 6.5: Регистрация разрешённых D-ссылок (до аудита мёртвых ссылок)

До вызова release-аудитора (Шаг 8d) убедиться, что все устойчивые ссылки на решения в prospective diff релиза живы. Запустить от корня репозитория:

```bash
python scripts/find_trace_refs.py --base main
```

- Живые `D##` (есть в реестре `.ai/DECISIONS.md`) — PASS; мёртвая ссылка — FAIL с file:line и списком незарегистрированных идентификаторов.
- Новое реальное продуктовое решение из релиза регистрируется в `.ai/DECISIONS.md` основным агентом/пользователем в формате реестра (идентификатор `D##` первым токеном строки) **до** аудита; технические ADR в dot_ai не создаются, чужие технические `D##` не создаются автоматически.
- Реальное новое решение вне установленного scope не удаляется как мусор: замечание и согласование с пользователем.
- Локальные номера требований/чекбоксов (`R##`, `C##.##`, `A##`, `X##`) не являются глобальными решениями и не регистрируются.
- В установленном проекте принимается его реестр/путь (`--registry`, `--root`); портальный реестр не навязывается.
- Аудит чистоты (Шаг 8d) запускается только после этого шага: проверка мёртвых ссылок работает по актуальному реестру.

### Шаг 7: Архивирование spec

Использовать `references/spec-archiving.md`.

Только для маршрута `spec`:

```bash
mkdir -p .ai/specs/archive/
git mv ".ai/specs/${spec_slug}.md" ".ai/specs/archive/${spec_slug}.md"
```

Для маршрута `small_fix` пропустить этот шаг.

### Шаг 8: Source-of-truth sync validation

Запустить валидатор синхронизации перед merge:

```bash
python scripts/validate_source_sync.py
```

- **FAIL (exit 1)** — drift между product source layer и local runtime layer. STOP: синхронизировать runtime-копии вручную по подсказкам валидатора, затем повторить.
- **WARN (exit 0)** — phantom-файлы или optional-расхождения. Продолжить с предупреждением, сообщить пользователю.
- **OK** — всё синхронизировано.

### Шаг 8a: Блокирующая чистота Python dot_ai

В репозитории dot_ai выполнить `python scripts/validate_no_comments.py` от корня. Ненулевой exit или ошибка токенизации — STOP до исправления. Проверяются все git-tracked `*.py`; строки и docstrings допускают `#`, исключений для shebang/encoding/pragma/noqa нет. Валидатор — локальный инструмент dot_ai, не поставляется установленным проектам.

### Шаг 8b: Memory audit (обязательный, advisory)

Использовать `references/memory-audit.md`. Запустить от корня репозитория:

```bash
python scripts/audit_skill_memory.py --version {version}
```

Отчёт сохраняется в `.ai/reports/memory/{version}.md` и включается в релизные артефакты (durable-путь, не временный каталог запуска).

Правила шага:

- **Выполнение обязательно**: пропуск аудита перед merge не допускается; ошибки выполнения самого аудита (недоступный git/база diff, сломанный YAML, usage-ошибки) — STOP до исправления.
- **Результаты advisory**: превышения лимитов памяти, дефекты формата, противоречия в содержимом, UNKNOWN tokenizer (с причиной) и рассинхрон mirrors не блокируют merge и не дают failed функциональной приёмки только из-за содержимого памяти.
- **Функциональные проверки остаются блокирующими**: advisory-статус памяти не ослабляет тест-гейты и остальные merge-проверки; красный функциональный тест по-прежнему STOP.
- **Пересчёт**: если после первого отчёта менялась память (LEARNINGS/EVALS) или YAML настроек — повторить запуск перед merge; актуальными считаются свежие счётчики, лимиты и хеши нового отчёта.

### Шаг 8c: Повторный tokenizer-preflight перед merge (после снимка)

Проверить, что после фиксации снимка параметров (Шаг 8b) не опубликована более новая стабильная версия tiktoken. Сохранить снимок запуска и повторить read-only preflight с ним:

```bash
python scripts/workflow_config.py --json > {run_temp}/run-snapshot.json
python scripts/check_tokenizer_updates.py --snapshot {run_temp}/run-snapshot.json --report-dir .ai/reports/dependencies
```

| Статус | Действие |
|---|---|
| `CURRENT` | Актуально; merge продолжается |
| `UPDATE_PENDING` | Новая stable найдена после снимка: отчёт фиксирует статус и новую версию; pin и снимок не меняются посреди запуска; эта гонка сама по себе не блокирует merge; обновление применяется в ENTRY-preflight следующего запуска; текущая версия не называется последней |
| `UNKNOWN` (источник недоступен/расходится) | Не блокирует merge и memory-аудит; фиксируется в отчёте |
| `UNKNOWN` (pin снимка не совпадает с текущей конфигурацией) | Снимок менялся посреди запуска: STOP — пересчитать память/отчёты по правилам Шага 8b, переснять снимок и повторить этот шаг |
| `INCOMPATIBLE` | Обновления нет; pin прежний; merge продолжается |

### Шаг 8d: Release cleanliness audit (обязательный, блокирующий по чистоте)

Использовать `references/cleanliness-audit.md`. Вызвать release-аудитора реальным запуском по host-политике (субагент/профиль `workflow-release-auditor`) с task-пакетом: repo_root, branch, diff_range (обычно `main..HEAD` + несмёрженные релизные артефакты Шагов 4–7), exemptions, helper_scripts (`scripts/find_trace_refs.py`, `scripts/audit_skill_memory.py`), report_path.

Правила шага:

- **Выполнение обязательно**: пропуск аудита чистоты перед merge не допускается; ответ `INSUFFICIENT_CONTEXT` — восполнить пакет и повторить вызов.
- **Вердикт `clean` обязателен для merge**; `blocked` (подтверждённые обязательные нарушения зон чистоты: введённый мусор/debug, мёртвая ссылка после Шага 6.5, изменение вне release-scope) — STOP до исправления и повторного аудита.
- **Memory-находки advisory**: не блокируют merge и не отменяют Шаги 8a–8c; ошибки выполнения самого аудита — реальные ошибки и STOP.
- **Возврат на ②**: замечания, требующие изменения кодовой логики, публичных контрактов или конфигурации, аудитор сам не чинит — основной агент возвращает их на шаг реализации. Ценное rationale и смысл public-docs сохраняются (в кодовых файлах комментарии запрещены целиком, rationale переносится в docs/commit).
- **Отчёт** сохраняется в `.ai/reports/release-audit/{version}.md` как релизный артефакт; после patch аудитора выполняются связанные проверки затронутых файлов (lint для `.py`, повторный memory-аудит при правке памяти).

### Шаг 9: Merge

Перед выполнением использовать `references/sufficiency-gate.md` и `references/merge-execution.md`.

Повторить `python scripts/validate_test_evidence.py` по итогам собственных version/audit/config изменений Шагов 4–8d: `reuse` либо выполненный и GREEN targeted/full rerun с зафиксированным supplement — условие sufficiency gate.

```bash
git add .ai/CHANGELOG.md .ai/release-notes/{version}.md {version-artifacts} ".ai/specs/archive/${spec_slug}.md"
git commit -m "docs: update CHANGELOG for {feature-name}"
git checkout main
git merge --no-ff {branch} -m "feat: {feature-name} ({version})"
git branch -d {branch}
```

Для маршрута `small_fix` не добавлять путь архива spec (release notes остаются в `git add`) и использовать merge message `fix: {summary} ({version})`.

### Шаг 9.5: Полная уборка ветки (после успешного merge)

Merge уже успешен — уборка не может его отменить. Использовать `references/merge-execution.md` (Post-merge Cleanup): сначала dry-run `python scripts/workflow_cleanup.py --branch-slug {branch-slug} --run-id {run-id} [--reference {final-manifest-or-report}]... [--orphans]`, проверить план (удаления, сохранения с причинами, перенос evidence), затем та же команда с `--apply`. Перед удалением referenced evidence переносится в `.ai/reports/evidence/` с обновлением ссылок в итоговых документах. Ненулевой exit или непустой `failures` — видимый отчёт пользователю; merge НЕ откатывается и не объявляется несуществующим.

### Шаг 10: Отчёт

Использовать `assets/merge-report-template.md`. После merge можно запустить `scripts/validate_merge_completion.py`.

```
✅ Merge завершён

Ветка:    {branch} → main
CHANGELOG: .ai/CHANGELOG.md обновлён
Version:   {version} синхронизирована
Spec:      .ai/specs/archive/{branch}.md
Tests:     {X} passed
```

Для маршрута `small_fix` вывести `Spec: не требуется (apply-small-fix)` и `Fix: .ai/fixes/{slug}.md`.

## Continuous Improvement

По завершении каждого запуска выполни Improvement Triage:

1. Задача решена без неоднозначностей → вывести `no_change`.
2. Обнаружен повторно применимый урок → добавить краткую запись в `LEARNINGS.md`.
3. Инструкции навыка привели к ошибке → сначала создать eval-кейс в `EVALS.md`.
4. Предлагать патч `SKILL.md` только если та же проблема может повториться.
5. Предпочитать замену или удаление устаревшего guidance добавлению новых правил.
6. Не обновлять `SKILL.md` до прохождения соответствующего eval.
