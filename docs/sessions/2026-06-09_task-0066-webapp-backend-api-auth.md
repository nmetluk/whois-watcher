# SESSION-0066 — WebApp backend: initData auth + read /api/webapp (TASK-0066)

**Дата:** 2026-06-09 · **Таск:** TASK-0066 · **Ветка:** task/0066-webapp-backend-api-auth
· **Исполнитель:** Grok (agent)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты.

## Задача

Реализовать backend-часть WebApp по ADR 043 / TASK-0066: точная валидация Telegram initData, aiohttp под-роутер /api/webapp/* (read-only), CORS + rate, health-score на бэкенде, серверная пагинация/фильтры для portfolio и прочие read-эндпойнты. Группы — пусто (TASK-0073).

## Выполнено

- Добавлены настройки `webapp_origin`, `webapp_initdata_ttl` (settings + .env.example).
- `src/bot/webapp/auth.py`: чистая `validate_init_data` (точный алгоритм: parse, data_check_string по \n, secret=HMAC(WebAppData, token), compare, auth_date TTL). aiohttp middleware (X-*-Init-Data / Authorization: tma ..., 401 на fail). Авто-регистрация/ touch User.
- `src/services/health_score.py`: `compute_health_score` по формуле из design/data.js (без jitter сида).
- `src/bot/webapp/api.py`: под-апп с роутами /portfolio (фильтры soon/crit/problem/... + q/sort/paginate, серверно), /domain/{id}, /dashboard, /calendar, /alerts (из sent_notifications), /settings, /groups (пусто), /wishlist. Шейпинг в точности по модели из design README. Использует существующие репозитории + get_session (как ARQ). CORS middleware только на configured origin.
- `src/bot/webhook.py`: `setup_webapp_on_main` в create_app (монтирует subapp).
- Тесты: `tests/unit/test_webapp_auth.py` — валидный (roundtrip), подделанный, просроченный, malformed (все проходят).
- PII: все эндпойнты скоупятся по user_id из initData.user.id.
- Нет миграций (существующие таблицы + wishlist).

## Изменённые/новые файлы

- `src/config/settings.py`
- `.env.example`
- `src/bot/webapp/__init__.py` (new)
- `src/bot/webapp/auth.py` (new)
- `src/bot/webapp/api.py` (new)
- `src/services/health_score.py` (new)
- `src/bot/webhook.py`
- `tests/unit/test_webapp_auth.py` (new)
- `docs/sessions/2026-06-09_task-0066-webapp-backend-api-auth.md` (this)

## Коммиты

(будут после push)

## Проверки

- pytest unit: 993 passed (включая новый тест)
- mypy src: clean (strict)
- ruff / black: clean на изменённых
- handoff claim: выполнен (ветка от свежего main)
- Полный pytest (unit) зелёный; интеграционные — требуют docker (не ломают).

## Что осталось / следующий шаг

- TASK-0067 (frontend foundation: Vite + токены + Telegram SDK + nginx статика)
- TASK-0070 (write actions: тогглы, add, mass)
- TASK-0071 audit (security-heavy: initData replay, CORS, PII, CSP)
- В /portfolio для сложных фильтров total — приблизительный (пост-фильтр); при необходимости — отдельный count в репозитории.
- health в dashboard/calendar — упрощён (нет полного join всех кэшей на 50k); для прод — оптимизировать или кэшировать health в user_domains.
- dev: для локального WebApp (vite) ставить WEBAPP_ORIGIN=http://localhost:5173

## Архитектурные решения / открытые вопросы

- Stateless initData на каждый запрос — как в ADR (дешево, безопасно). JWT позже если будет нагрузка.
- health-score — единственный источник (бэкенд), фронт только рендерит. Формула детерминированная.
- /groups всегда [] до 0073 — по явному указанию в таске.
- Нет цен (cost=0) — нет поля в модели; будет в будущем.
- Кэши (ssl/dns/email) фетчатся батчем на странице — N=50 ок; на 50k portfolio фронт использует пагинацию.

## PR

- Откроем после handoff status in_review + push ветки.
