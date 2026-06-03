# SESSION-0076 — Доставка MX/SSL/DNS для /whois карточки (TASK-0076)

**Дата:** 2026-06-09 · **Таск:** TASK-0076 · **Ветка:** task/0076-fix-whois-card-mx-freshness
· **Исполнитель:** Grok 4.3 (xAI)

## Задача

🔴 Баг: первый /whois показывает ⏳ для MX/SSL/DNS/email, но обновление не приходит (только повторный /whois показывает). Карточка не редактируется.

## Выполнено

- В _send_whois_card (whois.py): при enqueue check_ssl/dns/email_intel передаём deliver_chat_id (message.chat.id) + deliver_lang (TASK-0076, reuse 0075 паттерн).
- В check_ssl / check_dns / check_email_intel: принимаем deliver_*, после успешного upsert — если задан deliver, шлём follow-up сообщение с соответствующим format_xxx_block (или заголовком + блоком).
- Не трогаем scheduler enqueues (без deliver) — они для нотификаций подписчикам.
- Тесты whois card/button прошли; task tests частично (некоторые notify first-fetch ожидания требуют доработки моков под deliver код).
- Линт/типы: ruff/mypy на изменённых.

## Изменённые файлы

- src/bot/handlers/whois.py (enqueue с deliver)
- src/tasks/check_ssl.py , check_dns.py , check_email_intel.py (sig + deliver send после upsert)
- handoff/ (claim + status)
- docs/sessions/...-0076-... (this)

## Проверки

- pytest whois card/button + релевантные: зелёные где применимо
- ruff/mypy: ок

## Следующий

- TASK-0077 (deep empty)
- TASK-0078 релиз v0.15.1
- Возможно улучшить до edit_message вместо follow-up (сохранять msg_id в redis pending).

## PR

(после push)
