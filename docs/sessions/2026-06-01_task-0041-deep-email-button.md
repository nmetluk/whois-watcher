# SESSION-0041 — Кнопка «✉️ Глубокий e-mail» (TASK-0041)

**Дата:** 2026-06-01  
**Таск:** TASK-0041  
**Ветка:** task/0041-deep-email-button (чистая, после мержа 0042)  
**PR:** (будет)  
**Исполнитель:** Claude (Grok)

---

## Цель (из таска)

Реализовать кнопку «✉️ Глубокий e-mail» в карточке `/whois` (on-demand).

**Обязательно закрыть два долга TASK-0039:**

1. **DANE пустой** — прокинуть `mx_hosts` из `email_intel_cache` в `fetch_deep_email` / `check_email_deep`.
2. **Freshness-гейт** — перед enqueue `check_email_deep` проверять `email_deep_cache.next_check_at`. Свежий кэш → показать сразу; пустой/протух → «⏳ ищу…» + enqueue.

## План реализации

- Переиспользовать паттерн из TASK-0042 (`_show_subdomains_from_whois_card`).
- По возможности ввести общий on-demand helper (как обсуждалось в ревью 0042).
- Изменения:
  - `src/bot/keyboards.py` + локали — кнопка
  - `src/bot/handlers/whois.py` — хэндлер + freshness логика
  - `src/tasks/check_email_deep.py` — читать MX из базового кэша и передавать в `fetch_deep_email`
  - (опционально) `src/services/formatters.py` — `format_email_deep` если ещё нет
- Тесты на handler + freshness.

## Статус на старте

- `fetch_deep_email(domain, mx_hosts=...)` уже принимает `mx_hosts` (сделано в 0038/0039).
- `check_email_deep` пока зовёт без MX (явный TODO в коде).
- `email_deep_cache` с `next_check_at` существует.
- Кнопки on-demand на карточке уже есть (`subdomains`).

Готов начать код.

---

**Следующий шаг:** добавить кнопку + локали, затем handler с freshness gate, затем починить передачу MX в задаче.
