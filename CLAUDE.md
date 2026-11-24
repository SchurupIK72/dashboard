# Dashboard

Веб-дашборд для совместного путешествия по Вьетнаму (2 компании, 3 пользователя): список покупок, дела, учёт расходов со справедливым делением по чекам и вычетом личных трат (корм собаки), погода, курсы RUB/USD к VND и BTC/ETH с графиками. Python/FastAPI + SQLite + Jinja2/HTMX, запуск на VPS или локально в Docker.

---

## Workflow

**За сессию — один шаг.** Перед началом определить текущий шаг.
Основной маршрут использует ТЗ. Параллельный маршрут `small-fix` предназначен только для небольших фиксов без ТЗ и требует короткую постановку задачи из диалога (симптом/ожидаемое поведение/границы/проверка готовности); режим диалога (Default или Plan) не гейт.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  plan-release   │────►│implement-spec-stage│────►│ write-tests │────┐
│  ① ТЗ + Ветка   │     │ ② Реализация      │     │ ③ Тесты    │    │
└─────────────────┘     └──────────────────┘     └─────────────┘    │
                                                                     ▼
┌─────────────────┐                                            ┌──────────────────┐
│  apply-small-fix│───────────────────────────────────────────►│ integrate-release │
│ F① Fix          │                                            │  ④ Мерж           │
└─────────────────┘                                            └──────────────────┘
```

### Новая фича / крупный багфикс

| Шаг | Навык | ENTRY | EXIT |
| --- | --- | --- | --- |
| ① | plan-release | branch: `main` | `.ai/specs/{type}-v{version}-{slug}.md` создан, ветка `{type}/v{version}-{slug}` |
| ② | implement-spec-stage | spec + ⬜ этапы | все этапы ✅ |
| ③ | write-tests | все ✅ | тесты GREEN |
| ④ | integrate-release | GREEN | branch: `main`, spec в `archive/`, version artifacts синхронизированы |

### Небольшой фикс

| Шаг | Навык | ENTRY | EXIT |
| --- | --- | --- | --- |
| F① | apply-small-fix | branch: `main`, локальный фикс без ТЗ + короткая постановка (symptom/expected/scope/verification) | `fix/{slug}` + commit + проверка |
| ④ | integrate-release | `fix/*`, нет spec, нет uncommitted changes | branch: `main`, CHANGELOG обновлён |

### Правила переходов

1. **Нельзя пропускать шаги внутри выбранного маршрута** — каждый навык проверяет ENTRY
2. **Один шаг за сессию** — после завершения `/clear`
3. **Явный next_skill** — навык указывает следующий шаг
4. **`apply-small-fix` требует короткую постановку** — symptom/expected/scope/verification собираются из диалога в любом режиме (Default или Plan); режим UI не гейт
5. **Если навык ошибся** — зафиксировать, исправить, спросить
6. **Каждое ТЗ = новый релиз** — `plan-release` выбирает будущую SemVer-версию `MAJOR.MINOR.PATCH` и использует её в заголовке ТЗ, spec-файле и ветке: `{type}-v{version}-{slug}.md` и `{type}/v{version}-{slug}`
7. **Версия синхронизируется на merge** — `integrate-release` обновляет `.ai/CHANGELOG.md` и все найденные version artifacts проекта (`pyproject.toml`, `package.json`, `VERSION`, `__version__` и аналоги) до версии релиза

### Workflow State Validation

`scripts/validate_workflow_state.py --step {skill}` — ENTRY-проверка declared workflow state. Проверяет маршрут, spec, статусы этапов и version consistency. Не заменяет фактические проверки навыков.

---

## Решения проекта

Все проектные решения и границы — в `.ai/DECISIONS.md`.

---

## Структура

```
Dashboard/
├── src/dashboard/        ← FastAPI-приложение (routers, services, templates, static)
├── tests/                ← pytest (unit/, integration/)
├── data/                 ← SQLite (volume, не в git)
├── Dockerfile, docker-compose.yml
├── pyproject.toml        ← uv
├── .ai/                  ← ARCHITECTURE, CHANGELOG, DECISIONS, specs/, workflow.yaml
└── .claude/ .agents/ .codex/  ← dot_ai: навыки, агенты, правила
```
Каркас приложения пока не создан — появится первым релизом (`plan-release`).

## Технологии

| Технология | Версия | Назначение |
|---|---|---|
| Python 3.12 | 3.12 | Язык |
| FastAPI | — | Веб-API и страницы |
| SQLite | — | Хранилище (файл в volume) |
| Jinja2 + HTMX | — | Серверный UI без сборки фронтенда |
| Chart.js | — | Графики курсов |
| Docker Compose | — | Запуск локально и на VPS |
| uv | — | Пакетный менеджер |

## Конфигурация

`.env` файл:

```env
DATABASE_URL=sqlite:///data/dashboard.db
SECRET_KEY=change-me
TZ=Asia/Ho_Chi_Minh
```

---

## Навыки

| Навык | Шаг | Описание |
| --- | --- | --- |
| plan-release | ① | ТЗ по IEEE 29148 с версией релиза + ветка + коммит |
| apply-small-fix | F① | Небольшой фикс без ТЗ по короткой постановке из диалога (Plan или Default) |
| implement-spec-stage | ② | Реализация этапов ТЗ; после закрытия этапа — импакт-отчёт пользователю в чате |
| write-tests | ③ | Написание тестов |
| integrate-release | ④ | CHANGELOG + синхронизация версии + архив spec + merge |
| commit-helper | — | Conventional commits |
| skill-creator | — | Руководство по созданию навыков |
| playwright-testing | — | Браузерная проверка UI |

## Path-gated правила

`.claude/rules/` — инструкции загружаются автоматически при совпадении `paths:` с текущим файлом.

## Документация

| Документ | Путь | Описание |
| --- | --- | --- |
| Архитектура | `.ai/ARCHITECTURE.md` | Структура проекта |
| ТЗ | `.ai/specs/` | Технические задания |
| CHANGELOG | `.ai/CHANGELOG.md` | История изменений |
| Manifest | `.ai/dot_ai_install.json` | Метаданные установки dot_ai |

---

> **Один шаг за сессию. После — `/clear`. Каждый навык указывает `next_skill`.**
>
> **Обновление dot_ai:** `/install` повторно — manifest `.ai/dot_ai_install.json` обеспечит безопасный upgrade.
