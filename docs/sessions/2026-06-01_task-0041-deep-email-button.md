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

## Статус (2026-06-01, доработка по замечаниям архитектора)

Архитектор вернул на доработку. Основные правки выполнены:

**Закрыты оба долга из 0039 + anti-drift (основное замечание):**

1. ✅ **mx_hosts в DANE** — в `check_email_deep` теперь читаем `email_intel_cache.mx_records` и передаём `mx_hosts=...` в `fetch_deep_email`.
2. ✅ **Freshness gate** — в `_show_deep_email_from_whois_card` проверяем `email_deep_cache.next_check_at > now`.
3. ✅ **Anti-drift** — полностью убрал `getattr` на `EmailDeepCache` (прямой доступ + типизация `EmailDeepCache | None`), по аналогии с TASK-0045. Это было главное замечание.

**Дополнительно в доработке:**
- Убраны хаки с `.replace` на строках из subdomains
- Добавлены нормальные локали `deep_email.searching` / `cached_placeholder`
- Код стал чище и соответствует конвенциям проекта

**Осталось (следующие шаги):**
- Нормальный `format_email_deep` (сейчас заглушка)
- Юнит-тесты на хэндлер deep email
- Реальная проверка в Telegram
- PR + ответы на вопросы по стратегии отображения результата и общему on-demand хелперу

Готов к следующему раунду ревью.
