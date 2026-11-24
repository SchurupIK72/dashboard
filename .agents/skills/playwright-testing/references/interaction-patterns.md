# Interaction Patterns

Готовые сценарии взаимодействия с браузером. Каждый шаг: **действие → wait → snapshot/screenshot → assertion**. Используются только инструменты, реально доступные в сессии; отсутствующие — замещаются или фиксируются как ограничение.

## Базовый flow (любая страница)

```
1. browser_navigate(url)
2. browser_wait_for(text | textGone=<loader>)     # дождаться готовности
3. browser_snapshot()                              # структура + ref (action space)
4. browser_take_screenshot({ fullPage: true })     # визуал для контекста
5. browser_console_messages()                      # JS/CSP-ошибки → в файл
6. browser_network_requests()                      # failed API / 404 assets → в файл
```

`browser_snapshot` возвращает дерево с `ref` у каждого узла. **Все дальнейшие клики и ввод — по этому `ref`**, не по угаданному селектору.

## Form Interaction

```
1. browser_snapshot()                              # найти поля по ref
2. browser_type({ target: ref, text })             # поочерёдно для каждого поля
   (если в сессии есть инструмент заполнения форм одним вызовом — можно им)
3. browser_select_option({ target: ref, values })  # для выпадающих списков
4. browser_click({ target: ref-of-submit })
5. browser_wait_for(text=<success> | textGone=<form>)
6. browser_snapshot() + browser_take_screenshot()  # результат
7. Для невалидного ввода — assertion на сообщение об ошибке (видимо в snapshot)
```

## Modal Testing

```
1. browser_click({ target: ref-of-trigger })
2. browser_wait_for(text=<modal-title>)
3. browser_snapshot()                              # поддерево модалки, если инструмент
                                                   # поддерживает сужение области
4. Проверить контент, вкладки, кнопки внутри модалки
5. browser_click({ target: ref-of-close })         # или browser_press_key(Escape)
6. browser_wait_for(textGone=<modal-title>)         # модалка скрыта
```

## Tab Navigation

```
1. browser_snapshot() → собрать refs вкладок
2. Для каждой вкладки:
   a. browser_click({ target: ref-of-tab })
   b. browser_wait_for(text=<tab-content-marker>)
   c. assert: активная вкладка сменилась, контент обновился
3. Проверить переключение туда-обратно
```

## Authentication Flow

Только выделенные тестовые аккаунты из предусловий сценария; реальные пользовательские аккаунты запрещены.

```
1. (свежая browser-сессия) browser_navigate(<маршрут входа целевого проекта>)
2. browser_type по полям формы входа (refs из snapshot)
3. browser_click(submit)
4. browser_wait_for(text=<auth-indicator>)          # user-menu / logout / имя аккаунта
5. assert: редирект туда, куда ведёт вход, auth-индикатор виден
6. Проверить защищённую страницу: контент залогинен
7. Logout → assert: auth-индикатор исчез, возврат на маршрут входа
```

## Responsive (Адаптив)

Брейкпоинты — из исходников целевого проекта (`target-inventory.md`). Если в сессии есть инструмент смены viewport — прогнать каждую страницу на ≥3 размерах:

```
для каждого (w, h) из брейкпоинтов проекта:
  1. сменить viewport на (w, h)
  2. browser_snapshot()    # ловим сломавшуюся раскладку в структуре
  3. browser_take_screenshot()
  4. assert: нет горизонтального скролла, элементы не перекрываются,
     текст не обрезан, интерактивы доступны (tabindex/role корректны)
```

Инструмента viewport нет → responsive-evidence фиксируется как ограничение; не заявлять адаптив «проверенным» без него.

## Чтение точных значений из DOM/CSS

Когда нужны точные значения (цвета, отступы, размеры, видимость):

- Если в сессии есть инструмент вычисляемых стилей (evaluate-подобный) — вернуть JSON: computed styles, `getBoundingClientRect()`, `scrollWidth/clientWidth`. Это точнее любого суждения по скриншоту.
- Если такого инструмента нет — значения «на глаз» по скриншоту не заявляются как точные: зафиксировать ограничение.

См. [`visual-review.md`](visual-review.md).

## Waiting Strategies

- `browser_wait_for({ text })` — ждать появления текста (успех/результат).
- `browser_wait_for({ textGone })` — ждать исчезновения (loader, modal).
- Ожидание по времени — **последнее средство**, не заменяет явные ожидания по состоянию.
- После form-submit всегда ждать navigation/ответа перед snapshot.
