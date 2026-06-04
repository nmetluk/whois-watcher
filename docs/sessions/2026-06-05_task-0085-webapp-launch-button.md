# 2026-06-05 — TASK-0085: кнопка запуска WebApp в /start + /webapp (upstream из прод-сташа)

**Контекст.** Закрытие дрейфа main↔прод из
`2026-06-05_prod-webapp-button-missing-after-hotfix.md`: код кнопки WebApp
жил только в локальном stash на прод-машине. Выполнено архитектором
напрямую в main по решению владельца («задеплоить всё вместе»).
Реализация воспроизведена по спецификации из отчёта админа; smoke-проверка
дала ровно то поведение, что админ верифицировал на проде (4 кнопки,
текст «📱 Дашборд (WebApp)», url `https://…/app/`).

## Изменения

- `src/config/settings.py` — `@computed_field webapp_url`
  (`webhook_base_url.rstrip('/') + '/app/'`).
- `src/bot/keyboards.py` — `start_keyboard(lang, *, webapp_url=None)`:
  условная 4-я кнопка с `WebAppInfo`; новая `webapp_open_keyboard`.
- `src/bot/handlers/start.py` — `cmd_start` принимает `settings: Settings`
  (DI через `dp["settings"]`, как admin/version); новый `cmd_webapp`
  (`/webapp`, `/app`, `/dashboard`).
- `src/locales/{ru,en}.py` — `button.webapp`, `webapp.open_prompt`,
  `/webapp` в greeting и help.
- `webapp/vite.config.ts` — `base: '/app/'` (с комментарием про nginx).
- `tests/unit/test_keyboards.py` — 3 кнопки без url (+ проверка отсутствия
  web_app), 4 с url (+ `WebAppInfo.url`, `callback_data is None`),
  `webapp_open_keyboard`.

## Верификация

- pytest `test_keyboards.py` + `test_webapp_shape_domain.py`: 23 passed.
- ruff: All checks passed; black: 6 files unchanged.
- Smoke: `webapp_url == https://wwb.all-2-all.com:8443/app/`; rows=4,
  последняя кнопка — WebAppInfo с этим url; без url — 3.
- `npm run build`: зелёный, ассеты в `dist/index.html` с префиксом `/app/`.
- grep вызовов `cmd_start`/`start_keyboard`: других вызывающих нет
  (anti-drift правило при смене сигнатуры).
- mypy локально не прогнан (sandbox 3.10) — проверит CI.

## Открытое

- Контрольный редеплой из чистого main (DoD последний пункт) — за
  владельцем/админом: после него локальный stash на прод-машине можно
  дропнуть, дрейф закрыт.
- Опционально: зарегистрировать `/webapp` в BotFather menu button.
