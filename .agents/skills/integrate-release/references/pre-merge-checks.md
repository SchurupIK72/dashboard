# Pre-Merge Checks

Цель — убедиться, что merge не маскирует незавершённую работу и не переносит нестабильное состояние в `main`.

## Required Checks

| # | Проверка | PASS |
|---|---|---|
| 1 | Current branch | не `main` и не `master` |
| 2 | Route | определён как `spec` или `small_fix` |
| 3 | Worktree | `git status --porcelain` пустой до правки CHANGELOG/archive |
| 4 | Spec route | spec существует и все этапы реализации `✅` |
| 5 | Small-fix route | branch `fix/*`, spec отсутствует, фикс принят по host-политике и закоммичен после принятия, постановка `.ai/fixes/{slug}.md` доступна |
| 6 | Test evidence fitness | вердикт `scripts/validate_test_evidence.py`: `reuse` зафиксирован, либо выполнен обоснованный targeted rerun с дополнением манифеста (supplement), либо полный соответствующий suite GREEN; непустой tests diff и emoji — не условие и не доказательство |
| 7 | Base branch | локальный `main` доступен для checkout/merge |
| 8 | Memory audit | отчёт `.ai/reports/memory/{version}.md` сформирован; замечания памяти advisory (не блокируют merge) |
| 9 | Tokenizer ENTRY-preflight | выполнен ДО съёмки снимка параметров (до Шага 8b): `CURRENT` — без изменений; `UPDATE_AVAILABLE` — tiktoken-only обновление точной версией с последующими provisioning, offline/golden-проверками и пересчётом, и только затем снимок; `UNKNOWN`/`INCOMPATIBLE` не блокируют merge и не заявляют актуальность |
| 10 | Tokenizer re-check после снимка | выполнен после Шага 8b и до merge с сохранённым снимком (`--snapshot`): новая stable даёт `UPDATE_PENDING` в отчёте — pin и снимок неизменны, merge этой гонкой не блокируется, обновление применяется в preflight следующего запуска |

Для dot_ai обязательна блокирующая проверка `python scripts/validate_no_comments.py`: любой COMMENT token или ошибка чтения/токенизации останавливает merge. Политика и rationale: `docs/best_practice/python-comment-policy.md`.

Memory audit (`python scripts/audit_skill_memory.py --version {version}`, процедура — `references/memory-audit.md`) обязателен перед merge, но его результаты advisory: превышения лимитов, замечания формата, UNKNOWN tokenizer и рассинхрон mirrors не блокируют merge и не дают failed функциональной приёмки только из-за содержимого памяти. Ошибки выполнения самого аудита и функциональные проверки остаются блокирующими.

Tokenizer ENTRY-preflight (`python scripts/check_tokenizer_updates.py --report-dir .ai/reports/dependencies`, процедура — Шаг 1.5 навыка) выполняется до съёмки снимка параметров: совместимая новая stable закрепляется точной версией только после provisioning, offline/golden-проверок и пересчёта памяти/отчётов, и только затем фиксируется снимок запуска. Повторная проверка после снимка (Шаг 8c) с сохранённым снимком честно отражает новую stable как `UPDATE_PENDING`: pin и снимок не меняются, merge этой гонкой сам по себе не блокируется, обновление применяется в preflight следующего запуска. Недоступный или расходящийся официальный источник даёт `UNKNOWN` — не «последняя» и не блокировка memory-аудита; prerelease/dev/yanked исключены самой проверкой.

Test evidence fitness (`python scripts/validate_test_evidence.py`, процедура — Шаг 2 навыка) заменяет неизменный полный повтор всего набора: манифест ③ либо принятого F① сопоставляется с prospective merge-state по ревизии, хешам проверенных файлов/config/lock и recorded selection/sets. Совпавшая область и неизменённые dependencies дают `reuse`; version-only pin и объявлённая карта влияния — `targeted` только затронутых наборов с дополнением манифеста (supplement); изменённый config/lock и недоказуемые границы — `full`: старое доказательство не прикрывает новую конфигурацию. Отсутствующий манифест на spec-маршруте — `full`; для F① без ③ достаточно согласованного defect+related scope, полный набор не навязывается. Вердикт повторяется в Шаге 9 после собственных version/audit/config изменений; непустой tests diff и emoji не являются условием или доказательством.

## Stop Cases

Остановиться, если:

- есть uncommitted changes до начала integrate-release;
- route не определяется однозначно;
- пригодность evidence не доказана: требуемый targeted/full rerun не выполнен или красный;
- spec-route имеет незавершённый этап;
- apply-small-fix содержит spec или не выглядит как ветка `fix/*`;
- small_fix-ветка не прошла приёмку: постановка `.ai/fixes/{slug}.md` недоступна, приёмки не было или коммит сделан до принятия;
- merge потребует конфликтов, которые нельзя безопасно решить локально.

## After Checks

После PASS можно менять только:

- `.ai/CHANGELOG.md`;
- `.ai/release-notes/{version}.md`;
- version artifacts, обновляемые до release version;
- `.ai/specs/archive/{branch}.md` для `spec` route;
- release-артефакты аудитов (`.ai/reports/...`) и supplement манифеста evidence (сам targeted rerun — только по вердикту Шага 2);
- `MODULE_SIZE_REVIEWED` комментарии, если пользователь явно выбрал оставить крупный модуль.
