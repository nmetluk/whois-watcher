---
id: TASK-0035
title: Fan-out поддоменов — устранить N+1 и ordering-зависимый дедуп toggle'ов (ADR 038)
status: open
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0029]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-31
---

# TASK-0035 — Fan-out поддоменов: N+1 + дедуп toggle'ов (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Источник находки — `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
> (findings 🟡 в «Архитектура» и «Производительность»). **Включено в блокеры
> тега v0.12.0** (решение владельца 2026-05-31: влить все фиксы до релиза) —
> `TASK-0036` ждёт эту задачу.

## Цель

Сделать рассылку `notify_subdomain_changes` (1) без N+1 запросов и
(2) детерминированной по per-domain toggle'ам, независимо от порядка строк.

## Контекст / корень проблемы

`src/tasks/notify_subdomain_changes.py`:

1. **N+1.** В цикле по подписчикам — `user_repo.get_by_ids([user_id])` (один
   запрос на подписчика) и `NotificationRepository(session)` создаётся внутри
   цикла. Для registrable с N подписчиками — N+1 обращений к БД.
2. **Ordering-зависимый дедуп toggle'ов.** `get_subscribers_by_registrable`
   возвращает все `UserDomain`-строки registrable; дедуп по `user_id`. Если у
   пользователя несколько отслеживаемых строк под одним registrable (apex +
   поддомен, оба `track_subdomains=true`) с разными `notify_subdomain_new/
   removed`, применяются toggle'ы лишь первой успешно отправленной строки,
   остальные строки молча скипаются → инвариант ADR 038 «honoring per-domain
   toggle'ов» нарушается в этом сценарии.

## Изменения по файлам

- `src/tasks/notify_subdomain_changes.py`:
  - собрать `user_id` всех подписчиков → один `user_repo.get_by_ids(ids)` →
    map `user_id → User`; вынести `NotificationRepository(session)` из цикла.
  - агрегировать toggle'ы по пользователю: `notify_new = OR(notify_subdomain_new)
    по строкам юзера`, аналогично `notify_removed`; `is_muted` — если **любая**
    строка muted, гасим (или явно зафиксировать иную семантику в комментарии и
    ADR). Дедуп по `user_id` после агрегации (ordering-independent).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Пользователь с двумя строками одного registrable (`new=True/removed=False` и
  `new=False/removed=True`) → получает **одно** сообщение с **обеими** секциями
  (или по согласованной семантике), независимо от порядка строк.
- Ровно один `get_by_ids` на всю рассылку (нет N+1) — проверить числом вызовов.
- Регресс не сломан: дедуп, mute, blocked, журнал (см. TASK-0033).

## Требования к тестам

- Unit, моки со `spec`/`autospec`. Кейс на агрегацию toggle'ов и кейс на
  число запросов (отсутствие N+1).

## Definition of Done

- [ ] Код реализован по спецификации
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/` и вписан в `session:`
- [ ] `handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR: `docs/decisions.md` (ADR 038)
- Аудит: `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
- Связанные: TASK-0029 (реализация), TASK-0033 (тесты fan-out)
