---
id: TASK-0017
title: ARQ-задачи и scheduler email-intel + уведомления (ADR 036)
status: done
milestone: v0.10.0
adr: 036
area: code
depends_on: [TASK-0016]
branch: task/0017-email-intel-tasks-scheduler
owner: claude
session: docs/sessions/2026-05-30_task-0017_email_intel_tasks_scheduler.md
pr: ""
created: 2026-05-29
completed: 2026-05-30
---

# TASK-0017 — ARQ-задачи / scheduler / уведомления email-intel (ADR 036)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## 🔁 Ревью PR — ОТКЛОНЁН (уведомления не работают). Доработать

🔴 **Email-уведомления не отправятся никогда.** В `_enqueue_change_notices`
(`src/tasks/check_email_intel.py`) фильтр подписчиков сделан по флагам
`notify_email_mx` / `notify_email_spf` / `notify_email_dmarc` /
`notify_email_dkim` через `getattr(sub, user_flag, False)`. **Этих полей нет в
схеме** — TASK-0015 добавил только `track_email` и `notify_email_change`.
Значит `getattr(...)` всегда `False` → каждый change-type пропускается →
ни одно уведомление не ставится в очередь. Существующий toggle
`notify_email_change` при этом **не используется**.

Тест зелёный обманчиво: подписчик мокается голым `MagicMock`, который отдаёт
любой атрибут (`sub.notify_email_mx = True`), поэтому в тесте флаг «есть».
На реальном `UserDomain` его нет. (Тот же класс бага, что миграция на sqlite.)

**Как чинить (выровнять по ADR 036 — один toggle):**

- В `_enqueue_change_notices` и `send_email_change_notice` гейтить подписчика
  по **`notify_email_change`** (плюс уже корректные `is_muted` и `track_email`),
  а НЕ по несуществующим `notify_email_*`. Change-type (`mx_changed`/`spf_changed`/
  …) оставить — он нужен для текста уведомления, но НЕ как отдельный toggle.
- НЕ заводить гранулярные `notify_email_*` поля (ADR 036 закладывал один
  toggle `notify_email_change`; гранулярность — потенциальный отдельный ADR
  позже, не сейчас).
- **Тесты:** подписчиков мокать с `MagicMock(spec=UserDomain)` или строить
  реальные объекты `UserDomain`, чтобы отсутствующий/опечатанный атрибут падал,
  а не проходил молча. Добавить кейс: `notify_email_change=False` → уведомление
  НЕ ставится; `True` → ставится.

После правки прогнать весь `pytest` (с `CI=1`), убедиться, что путь enqueue
реально срабатывает на объекте со схемой `UserDomain`.

## Цель

Подключить сбор email-intel в очередь ARQ: периодическая проверка, запись в
`email_intel_cache`, расчёт diff и отправка уведомлений per-domain.

## Контекст

ADR 036. По образцу SSL-стека (`check_ssl`, `ssl_scheduler`,
`ssl_reminders_scheduler`, `notify_ssl_changes`) и DNS-стека.

## Изменения по файлам

- `src/tasks/` (по образцу `check_ssl.py` / `ssl_scheduler.py` /
  `notify_ssl_changes.py`):
  - `check_email_intel.py` — фоновая проверка одного домена: резолв
    (TASK-0016), upsert в кэш, diff, enqueue уведомлений. Защита от
    задвоения redis-флагом (как `*_in_progress`).
  - `email_intel_scheduler.py` — выбор доменов к проверке по `next_check_at`
    среди тех, у кого `track_email=true`.
  - `notify_email_changes.py` — рассылка подписчикам с `notify_email_change`
    и не `is_muted`; формат через локали.
- `src/tasks/arq_config.py` — регистрация задач/крона.
- Сервис-слой/`services/` — при необходимости фасад, хэндлеры тонкие.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `is_muted` гасит email-уведомления.
- Первая загрузка (`old=None`) не шлёт уведомление (пустой diff).
- Только переход reachable→unreachable значим; повтор не дублирует.
- Никаких sync-вызовов/блокировок loop; всё через ARQ.

## Требования к тестам

- `tests/unit/test_check_email_intel_task.py`,
  `test_email_intel_scheduler*.py`, `test_send_email_notice*.py` — по образцу
  ssl/dns task-тестов (мок redis/боты).

## Definition of Done

- [ ] Задачи/scheduler/уведомления подключены и зарегистрированы в ARQ
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 036; SSL-стек в `src/tasks/` как образец; ADR 029 (toggle'ы/mute)
