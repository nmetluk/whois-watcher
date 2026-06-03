---
id: TASK-0066
title: WebApp backend — initData auth + read JSON API (/api/webapp)
status: open
milestone: v0.16.0
adr: 043
area: code
depends_on: []
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0066 — WebApp backend: auth + read API (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 043; дизайн/модель данных — `design/webapp/v1/README.md`.

## Цель

Расширить существующий aiohttp-app (`src/bot/webhook.py`) под-роутером
`/api/webapp/*` (JSON) с auth через Telegram `initData` и read-эндпойнтами.

## Изменения по файлам

- `src/bot/webapp/auth.py` — валидатор `initData`: HMAC-SHA256, ключ
  `HMAC_SHA256(bot_token, "WebAppData")`; проверка `auth_date` свежести
  (`webapp_initdata_ttl`, дефолт 24ч). Парсит `user.id` → наш `users`.
  aiohttp-middleware/декоратор: невалидно/просрочено → 401.
- `src/bot/webapp/api.py` — read-эндпойнты (тонкие, через сервисы/репозитории):
  `GET /api/webapp/portfolio` (серверная пагинация/поиск/фильтр/сортировка/
  группировка — фильтры из `design/webapp/v1/app/screen-list.jsx` `FILTERS`),
  `GET /api/webapp/domain/{id}` (Обзор/WHOIS/SSL/DNS/Email/Поддомены из кэшей),
  `GET /api/webapp/dashboard`, `GET /api/webapp/calendar?month=`,
  `GET /api/webapp/alerts`, `GET /api/webapp/settings`, `GET /api/webapp/groups`,
  `GET /api/webapp/wishlist`. JSON-форма ответа домена — по модели из README
  (раздел «Структура объекта домена»).
- `src/services/health_score.py` — health-score (перенести формулу из
  `design/webapp/v1/app/data.js`, блок `let health=100…`) на бэкенд (один
  источник правды).
- `src/bot/webhook.py` — зарегистрировать под-роутер в `create_app`.
- `src/config/settings.py` — `webapp_origin`, `webapp_initdata_ttl`.
- CORS только на `webapp_origin`; rate-limit (переиспользовать `Limits`).

## Миграции БД

Скорее всего нет (используем существующие таблицы). Если «группы/теги» нет в
модели — мелкая миграция (проверить `src/db/models.py`).

## Инварианты (защитить тестами)

- initData с валидной подписью → ок; подделанная/просроченная → 401 (тест-вектор
  Telegram; валидатор — чистая функция).
- `/portfolio` отдаёт только домены текущего пользователя (PII-скоуп);
  пагинация/фильтры — на сервере.
- health-score совпадает с дизайн-формулой на эталонных данных.
- Хэндлеры тонкие (через сервисы), не сырой SQL.

## Definition of Done

- [ ] Auth + read-эндпойнты + health-score; CORS/rate-limit
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `design/webapp/v1/README.md`; `src/bot/webhook.py`,
  `src/services/domains.py`, репозитории кэшей.
- Связанные: TASK-0067 (frontend), 0070 (write).
