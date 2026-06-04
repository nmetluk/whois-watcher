---
id: TASK-0083
title: 🟠 WebApp security — initData TTL, dev-initData-в-URL, CORS-preflight, raw SQL, CSP
status: in_review
milestone: v0.16.0
adr: 043
area: code
depends_on: []
branch: task/0083-webapp-security-hardening
owner: ""
session: docs/sessions/2026-06-11_task-0083-webapp-security-hardening.md
pr: https://github.com/nmetluk/whois-watcher/pull/57
created: 2026-06-10
---

# TASK-0083 — WebApp security hardening (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🟠 Блокеры тега v0.16 (аудит 0071: F3–F7).

## Объём (5 пунктов)

### F3 — initData TTL по умолчанию 24ч → слишком большое replay-окно
`settings.webapp_initdata_ttl` дефолт `86400`. Сменить дефолт на **`3600`** (1ч).
`.env.example` — пояснение + пример. (Nonce-стора нет — короткий TTL и есть
защита от реплея; задокументировать как принятый риск, F10.)

### F4 — dev-fallback initData через query-param активен в проде
`auth.py::_extract_init_data` принимает `?initData=`/`?_initData=` без проверки
окружения (утечка initData в URL/логи/Referer). **Гейт за
`settings.environment == "development"`** (прокинуть environment в middleware/
extractor) или убрать query-param-путь совсем. По умолчанию в prod — только
заголовки.

### F5 — CORS-preflight ломается при cross-origin
Порядок middleware: `auth` внешний → `OPTIONS` без initData получает 401 до
`cors_mw`. **Пропускать `OPTIONS` в auth-middleware** (вернуть `handler(req)`/
ранний выход до валидации initData для метода OPTIONS), либо поставить `cors_mw`
внешним. Проверить, что preflight отдаёт 204 с корректными CORS-заголовками.

### F6 — raw `sa_delete(UserDomain)` в хэндлере `remove_domain`
Вынести удаление в `DomainRepository` (напр. `remove_for_user(user_id,
domain_id)`), хэндлер зовёт репозиторий (конвенция «БД только через
репозитории»). Поведение/скоуп сохранить.

### F7 — нет CSP на отдаваемом HTML mini-app
Добавить строгий `Content-Security-Policy` в nginx-конфиг для статики mini-app
(`default-src 'self'`; разрешить Telegram WebApp SDK
`https://telegram.org`/`https://web.telegram.org` при необходимости; шрифты/
иконки — по факту использования). Документировать в `docs/deployment.md`.

## Инварианты (тестами)

- F3: дефолт TTL == 3600 (тест на значение Settings).
- F4: при `environment="production"` query-param initData **игнорируется**
  (только заголовки); при `development` — принимается. Тесты на оба режима.
- F5: `OPTIONS` на `/api/webapp/*` без initData → 204 + CORS-заголовки (не 401).
- F6: `remove_domain` идёт через `DomainRepository`; тест на скоуп (нельзя
  удалить чужой домен).
- F7: nginx-CSP — конфиг + запись в deployment.md (проверяется ревью).

## Definition of Done

- [ ] F3–F7 закрыты; **полный `pytest` зелёный** + тесты F3/F4/F5/F6;
      `ruff`/`black`/`mypy`
- [ ] Реальная проверка в Telegram (вход работает; preflight ок при cross-origin
      если применимо); per-session отчёт; `handoff.py validate`; PR

## Ссылки

- ADR 043; `src/bot/webapp/{auth,api}.py`, `src/config/settings.py`,
  `src/db/repositories/domains.py`, nginx-конфиг/`docs/deployment.md`;
  аудит F3–F7.
