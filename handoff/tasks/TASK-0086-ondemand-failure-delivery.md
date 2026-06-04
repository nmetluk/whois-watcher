---
id: TASK-0086
title: 🟡 On-demand задачи при фейле сообщают пользователю об ошибке (не молчат)
status: done
milestone: v0.16.1
adr: 040
area: code
depends_on: []
branch: main (прямой фикс архитектора, по решению владельца)
owner: architect
session: docs/sessions/2026-06-05_task-0086-ondemand-failure-delivery.md
pr: —
created: 2026-06-05
---

# TASK-0086 — Доставка ошибки on-demand проверок (ADR 040)

> Урок инцидента `2026-06-05_diagnosis-ondemand-email-prod.md`: задачи с
> `deliver_chat_id` (TASK-0075/0076) досылали результат **только при
> успехе**. При фейле (crt.sh лежит, DNS-сбой) — «⏳ ищу…» и тишина,
> что неотличимо от сломанной доставки. Любой сетевой сбой на проде
> выглядит как регрессия 0075.

## Объём

- Новый помощник `src/tasks/_ondemand.py::deliver_ondemand_failure(ctx,
  deliver_chat_id, deliver_lang, *, kind, domain)` — локализованное
  сообщение о фейле; никогда не бросает; no-op без `deliver_chat_id`
  (периодические запуски не затронуты).
- Вшит в fail-paths всех 5 задач с `deliver_chat_id`:
  `check_subdomains` (error + unexpected), `check_email_deep` (error +
  unexpected), `check_email_intel`, `check_ssl`, `check_dns`.
- Локали ru/en: `tasks.deliver.failed.{subdomains,email_deep,email,dns,ssl}`.

## Инварианты (защищены тестами)

- Фейл + `deliver_chat_id` → одно сообщение об ошибке в чат (реальный `t()`).
- Фейл без `deliver_chat_id` (scheduler) → тишина, как раньше.
- Ошибка самой доставки (бот заблокирован) не роняет задачу.
- Все kind'ы рендерятся реальным `t()` в ru и en (без мока — урок TASK-0046),
  punycode → unicode.

## DoD

- [x] 17 новых тестов (15 helper + 2 wiring check_subdomains); смежные юнит-тесты зелёные
- [x] ruff / black по изменённым файлам — чисто (mypy — CI)
- [ ] Реальная проверка в Telegram: нажать кнопку при недоступном источнике → приходит «⚠️ Не удалось…»
