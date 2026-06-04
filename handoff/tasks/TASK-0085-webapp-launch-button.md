---
id: TASK-0085
title: 🟢 WebApp — кнопка запуска в /start + команды /webapp + vite base '/app/'
status: done
milestone: v0.16.1
adr: 043
area: code
depends_on: []
branch: main (прямой hotfix архитектора, по решению владельца)
owner: architect
session: docs/sessions/2026-06-05_task-0085-webapp-launch-button.md
pr: —
created: 2026-06-05
---

# TASK-0085 — Кнопка запуска WebApp в /start + прямые команды (ADR 043)

> Закрытие дрейфа main↔прод: код кнопки жил только в локальном stash на
> прод-машине (см. `docs/sessions/2026-06-05_prod-webapp-button-missing-after-hotfix.md`)
> и был восстановлен админом вручную после редеплоя 77819f8. Этот таск
> формализует код в main. Выполнен архитектором напрямую (владелец хочет
> задеплоить всё вместе одним редеплоем).

## Объём

- `Settings.webapp_url` — computed property (`webhook_base_url` + `/app/`),
  единая точка как `webhook_url`.
- `start_keyboard(lang, *, webapp_url=None)` — 4-я кнопка
  «📱 Дашборд (WebApp)» через нативный `WebAppInfo` (открывается внутри
  Telegram, initData передаётся автоматически). Без url — прежние 3 кнопки.
- `webapp_open_keyboard` + хэндлер `cmd_webapp` для `/webapp`, `/app`,
  `/dashboard`.
- Локали ru/en: `button.webapp`, `webapp.open_prompt`, упоминание
  `/webapp` в `start.greeting` и `help.body`.
- `webapp/vite.config.ts`: `base: '/app/'` (nginx `location /app/`,
  same-origin `/api/webapp/*`, CSP `'self'`).
- Тесты: `test_keyboards` — 3 кнопки без url / 4 с url + `WebAppInfo.url`,
  `webapp_open_keyboard`.

## DoD

- [x] pytest (test_keyboards 23 passed), ruff, black — чисто
- [x] smoke: `Settings.webapp_url` → `https://…/app/`; клавиатура 4/3 кнопки
- [x] `npm run build` — ассеты с префиксом `/app/`
- [ ] контрольный редеплой из чистого main: кнопка на месте БЕЗ ручных правок
      (это и есть закрытие дрейфа — проверяет владелец/админ)
