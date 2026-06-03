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

## Готовые факты (сверено архитектором)

- `settings.bot_token` — `SecretStr` (`.get_secret_value()`).
- `create_app(*, bot, dp, settings, redis)` (`src/bot/webhook.py`) — расширять
  тут: добавить роуты в `app` до `return`. Webapp-хэндлеры берут БД через
  `get_session()` (как ARQ-задачи) и существующие репозитории/сервисы.
- ⚠️ **Модели «групп/тегов» в БД НЕТ** (`domain.groups[]` из дизайна не на чём
  строить). Это **отдельная схема** → **TASK-0073** (groups/tags). Здесь:
  `/groups` отдаёт пусто, `/portfolio?group=` без группировки, пока 0073 не
  влит. Не делать суррогат.

## Точный алгоритм валидации initData (RFC Telegram — не перепутать ключ/сообщение)

```
1. Разобрать initData (querystring) в пары; извлечь и убрать поле `hash`.
2. data_check_string = пары `key=value`, отсортированные по ключу, склеенные '\n'.
3. secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)   # КЛЮЧ = "WebAppData"!
4. calc = hexdigest( HMAC_SHA256(key=secret_key, msg=data_check_string) )
5. hmac.compare_digest(calc, hash)  # constant-time
6. auth_date: now - auth_date <= webapp_initdata_ttl (иначе 401, защита от replay)
```
Порядок key/msg в шаге 3 критичен (перепутать = байпас или тотальный отказ).
Тест — на известном векторе Telegram (валидный + подделанный + просроченный).

## Изменения по файлам

- `src/bot/webapp/auth.py` — валидатор `initData` по алгоритму выше; парсит
  `user.id` → наш `users`. aiohttp-middleware/декоратор: невалидно/просрочено
  → 401. Чистая функция валидации (для теста).
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
