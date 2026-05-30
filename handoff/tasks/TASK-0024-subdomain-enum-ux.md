---
id: TASK-0024
title: UX — команда /subdomains + opt-in отслеживание + локали (ADR 037)
status: open
milestone: v0.11.0
adr: 037
area: code
depends_on: [TASK-0023]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-30
---

# TASK-0024 — UX subdomain enumeration (ADR 037)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Команда `/subdomains <domain>`: показать найденные поддомены (read-only) и дать
**opt-in** — взять выбранные на отслеживание через существующий `/add`-путь.

## Контекст

ADR 037. crt.sh-запрос медленный → команда отвечает «ищу…» и ставит ARQ-задачу
`check_subdomains` (TASK-0023); по готовности — список с кнопками.

## Изменения по файлам

- `src/bot/handlers/` — новый хэндлер `/subdomains` (тонкий): валидация домена
  (ADR 035, guard на публичный суффикс/мусор), запрос по registrable, ответ
  «ищу…», enqueue `check_subdomains`; рендер кэш-результата если свежий (TTL).
- Рендер списка + inline-кнопки «отслеживать» (по поддомену или пачкой) —
  при нажатии идём в существующий `/add`-путь (`DomainService.add_for_user` /
  promote, ADR 034/035). **Соблюсти лимит 50k** (ADR 011) — при превышении
  понятная ошибка, без частичного мусора.
- `src/bot/keyboards.py` / `states.py` — клавиатура выбора/подтверждения.
- `src/locales/ru.py`, `en.py` — **все** новые строки (заголовок списка,
  «ищу…», «ничего не найдено», «crt.sh временно недоступен», кнопки). Инвариант
  `test_all_ru_keys_present_in_en`.
- Зарегистрировать команду в роутере и (опц.) в меню BotFather-доках.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `/subdomains` не падает на мусорном/IDN-вводе и на пустой выдаче.
- crt.sh недоступен → понятное сообщение, не ошибка.
- Opt-in идёт через `/add`-путь; лимит 50k соблюдён; авто-добавления нет.
- `test_all_ru_keys_present_in_en` зелёный.
- Моки хэндлеров/сервисов — со `spec`/`autospec` (anti-drift, CLAUDE.md);
  покрыть путь кнопки opt-in → `/add` (callback), чтобы дрейф сигнатур падал.

## Требования к тестам

- `tests/unit/test_subdomains_handler.py` (+ рендер списка, opt-in callback,
  degradation). Real-world проверка в Telegram желательна.

## Definition of Done

- [ ] `/subdomains` работает: список + opt-in через `/add`; degradation; локали ru/en
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный
- [ ] После 0022–0024 — релиз v0.11.0

## Ссылки

- ADR 037; ADR 035 (registrable/guard), ADR 034 (promote), ADR 011 (лимит 50k).
