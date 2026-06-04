# 2026-06-05 — Hotfix: WebApp показывал demo вместо реальных доменов (500 из-за дрейфа полей EmailIntelCache)

**Контекст.** Ручная проверка на проде: домены есть в `/list`, но WebApp
показывает demo; реальные данные загрузились только на «Алертах».
Фикс — архитектором напрямую в main (по прецеденту сессии
2026-06-05_hotfix-webapp-design-fidelity).

## Диагноз

`_shape_domain` (`src/bot/webapp/api.py`) обращался к **несуществующим
полям** `EmailIntelCache`: `email.mx`, `email.dmarc`, `email.spf`,
`email.spf_all`, `email.dkim`. Реальные поля модели (ADR 036):
`mx_records`, `dmarc_policy`/`dmarc_subpolicy`, `spf_record`/`spf_mode`,
`dkim_selectors`. Прямое обращение → `AttributeError` → 500 на
**`/portfolio`, `/domain/{id}`, `/dashboard`** (все три используют шейпер)
для любой страницы, где хоть у одного домена есть строка email-кэша —
т.е. практически всегда (email-intel работает с v0.10).

`/alerts` email-кэш не трогает — поэтому «Алерты» работали. Симптом
сходится 1:1.

Маскировка: demo-fallback в `ListScreen.catch` (хвост TASK-0082)
подменял 500 на «Демо» — пользователь видел demo.ru вместо ошибки.
Тестов на `_shape_domain` не существовало.

**Это третий инцидент того же anti-drift-класса** (TASK-0017 —
несуществующие `notify_email_*`; TASK-0020 — дрейф сигнатуры `cmd_list`).
Плюс прямое нарушение правила CLAUDE.md: «`getattr(obj, "field", default)`
на ORM-объекте — красный флаг» — в коде было и это.

## Фикс

- `_shape_domain`: email-ветка переписана на реальные поля модели;
  без `getattr`-дефолтов.
- `tests/unit/test_webapp_shape_domain.py` — 4 теста на **реальных
  инстансах ORM-моделей без моков** (минимум, пустой email-кэш,
  полный email-кэш, SSL+DNS). Контрольный прогон на старом коде:
  2 failed — тест ловит баг.
- `ListScreen`: demo-fallback удалён → error-state (`tg-empty2`,
  сообщение + «Повторить») и empty-state; `App.tsx`: `DomainScreen`
  получает реальный объект домена (хардкод `demoD` удалён), заголовок
  карточки — имя домена.

## Верификация

- pytest: `test_webapp_shape_domain` 4 passed (+ `test_webapp_auth` 5 passed).
- На старом коде тест падает (red→green подтверждён).
- ruff по изменённым файлам: чисто (2 SIM102 в api.py — pre-existing, чужой регион).
- black: мои регионы чисты; найден pre-existing формат-дрейф в api.py
  (регионы ~951/986 — вероятно, след коммита c5a46f4 с `--no-verify`).
- `npm run build` — зелёный.
- mypy локально не прогнан (sandbox Python 3.10 < 3.11) — проверит CI.

## Хвосты

1. Pre-existing формат-дрейф black в `api.py` (чужие регионы) — поправить
   при следующем таске по webapp-API, либо `pre-commit run --all-files`.
2. Аудит TASK-0071 пропустил и этот дрейф, и отсутствие тестов на шейпер —
   в чек-лист аудита добавить «шейперы/форматтеры покрыты тестами на
   реальных моделях».
3. Остальные хвосты прежних сессий в силе (кнопка /start не в main,
   vite base '/app/', сабсеттинг шрифта, eslint).

## Деплой

Миграций нет. Бекап + редеплой по стандартной процедуре. После деплоя —
ручная проверка: список доменов и дашборд показывают реальные данные.
