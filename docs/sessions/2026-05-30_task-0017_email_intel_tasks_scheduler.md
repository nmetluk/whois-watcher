---
date: 2026-05-30
task: TASK-0017
title: Email-intel ARQ задачи и scheduler
author: claude
---

# TASK-0017: Email-intel ARQ задачи и scheduler (ADR 036)

## Цель

Подключить сбор email-intel в очередь ARQ: периодическая проверка, запись в
`email_intel_cache`, расчёт diff и отправка уведомлений per-domain.

## Выполнено

### ARQ-задачи

- **`src/tasks/check_email_intel.py`** — проверка одного домена:
  - Redis-флаг `email_intel_check_in_progress:<domain>` для защиты от задвоения
  - Успех → upsert в кэш + diff + enqueue уведомлений
  - Ошибка → update_fail + became_unreachable (только при переходе)
  - Первая проверка (old=None) не шлёт уведомления

- **`src/tasks/email_intel_scheduler.py`** — cron scheduler:
  - Bootstrap: создание записей для новых доменов с track_email=true
  - Выборка due-доменов по next_check_at среди подписчиков
  - Enqueue в check_email_intel

- **`src/tasks/notify_email_changes.py`** — уведомления:
  - 6 типов изменений: mx_changed, spf_changed, dmarc_changed, dkim_changed,
    became_unreachable, became_reachable
  - Respect is_muted/track_email/per-domain toggle'ы
  - Форматирование через локали

### Конфигурация

- **`src/tasks/arq_config.py`** — регистрация задач:
  - Импорты check_email_intel, email_intel_scheduler_tick, send_email_change_notice
  - Cron job: каждые 5 минут, run_at_startup=True

### Локали

- **`src/locales/ru.py`** и **`src/locales/en.py`**:
  - notify_config.type.*: track_email, email_mx, email_spf, email_dmarc, email_dkim
  - notifications.email_change.*: тексты уведомлений

### Тесты

- **`tests/unit/test_check_email_intel_task.py`** — 8 тестов:
  - Skip при удержанном Redis-флаге
  - First fetch не шлёт уведомления
  - MX change enqueue для подписчиков
  - Muted подписчик не получает уведомления
  - **notify_email_change=False не шлёт уведомления** (ревью-фикс)
  - First failure → became_unreachable + enqueue
  - Repeat failure не дублирует уведомления
  - NXDOMAIN не enqueue

- **`tests/unit/test_email_intel_scheduler_task.py`** — 3 теста:
  - Bootstrap SQL executed
  - Enqueue due domains
  - Skip when nothing due

Все тесты прошли (11/11), полный suite — 780 passed.

## Инварианты (защищены тестами)

- `is_muted` гасит email-уведомления ✓
- Первая загрузка (`old=None`) не шлёт уведомление ✓
- Только переход reachable→unreachable значим ✓
- Никаких sync-вызовов/блокировок loop ✓

## Сложности

1. **`spf_record` vs `spf_raw`**: в модели БД поле называется `spf_record`,
   а не `spf_raw`. Исправлено в коде и тестах.

2. **Mypy Literal типы**: `spf_mode` и `dmarc_policy` — строки, а типы
   ожидают Literal. Добавлены `# type: ignore[arg-type]` для совместимости.

3. **Unused variables**: в notify_email_changes.py остались unused imports
   после упрощения (cache_repo, cache). Удалены.

## 🔁 Ревью-фикс (первый PR отклонён)

**Проблема:** использовались несуществующие поля `notify_email_mx`/`spf`/`dmarc`/`dkim`,
которых нет в схеме UserDomain. В TASK-0015 добавлены только `track_email` и
`notify_email_change` (один toggle по ADR 036).

**Исправлено:**
- `_enqueue_change_notices`: гейт по `notify_email_change` вместо гранулярных полей
- `_TYPE_MAP` в `notify_email_changes.py`: упрощён до `(locale_key, notif_type)`
- Тесты: добавлен `spec=UserDomain` к MagicMock, тест для `notify_email_change=False`

**Коммит:** `0c97851` — fix(TASK-0017): исправить гейт notify_email_change (ревью-фикс)

## PR

https://github.com/nmetluk/whois-watcher/pull/new/task/0017-email-intel-tasks-scheduler

**Статус**: готов к ревью, все тесты зелёные, handoff validate OK.
