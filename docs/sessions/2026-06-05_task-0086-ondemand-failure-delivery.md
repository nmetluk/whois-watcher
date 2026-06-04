# 2026-06-05 — TASK-0086: on-demand задачи сообщают об ошибке, а не молчат

**Контекст.** Инцидент «поддомены не присылаются, MX пуст, deep email
нулевой»: код доставки оказался идентичен рабочему v0.15.2 — корень на
проде (worker/egress, см. `2026-06-05_diagnosis-ondemand-email-prod.md`).
Но обнажился системный пробел: при фейле on-demand задачи пользователь не
получает **ничего** — сетевой сбой неотличим от сломанной доставки.
Выполнено архитектором напрямую в main («заводи и сразу делай»).

## Изменения

- `src/tasks/_ondemand.py` (новый) — `deliver_ondemand_failure`:
  локализованное сообщение о фейле; не бросает; no-op без chat_id;
  защита от неизвестного `kind`.
- Вшит в fail-paths: `check_subdomains` (SubdomainEnumError + внешний
  except), `check_email_deep` (DeepEmailError + внешний except),
  `check_email_intel` (после `_handle_failure`), `check_ssl` (после
  `_handle_failure`), `check_dns` (error-ветка persist).
- Локали ru/en: `tasks.deliver.failed.*` (5 ключей, с {domain}).

## Верификация

- `tests/unit/test_ondemand_failure_delivery.py` — 15 тестов: все kind'ы
  × ru/en через **реальный t()** (урок TASK-0046), punycode→unicode,
  no-op пути, ошибка доставки не роняет задачу. Бот — `AsyncMock(spec=Bot)`.
- `test_check_subdomains_task.py` — 2 wiring-теста: фейл с deliver_chat_id
  шлёт ошибку (chat_id, текст с crt.sh), без — молчит.
- Смежные юнит-тесты (ssl/dns/email/subdomain/keyboard/webapp): 470 passed;
  6 падающих — pre-existing сбои локальной среды (Python 3.10 + pip-версии
  вместо uv.lock), падают и на нетронутом коде — CI на 3.11 источник правды.
- ruff/black по изменённым файлам — чисто. Замечено (не трогал): pre-existing
  ASYNC240 в `backup_postgres.py` под новым ruff.

## Поведенческий контракт

- Периодические запуски (scheduler, без `deliver_chat_id`) — поведение
  не изменилось ни на байт.
- Один фейл → одно сообщение; дедуп повторных запусков обеспечен
  существующим redis-guard'ом (`*_in_progress`).

## Хвосты

- Real-world проверка в Telegram после редеплоя (DoD, за владельцем).
- В чек-лист аудита: «fail-path on-demand задач имеет пользовательскую
  обратную связь».
