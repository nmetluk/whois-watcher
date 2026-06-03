# SESSION-0077 — Диагностика и фикс глубокого e-mail (TASK-0077)

**Дата:** 2026-06-09 · **Таск:** TASK-0077 · **Ветка:** task/0077-fix-deep-email-empty
· **Исполнитель:** Grok 4.3 (xAI)

## Задача

🔴 "Глубокий e-mail" всегда пустой, даже на повторном запросе (кэш свежий).

## Выполнено

- В fetch_deep_email: установлены публичные nameservers 1.1.1.1/8.8.8.8 (системный resolver в контейнере может не резолвить).
- Добавлены диагностические логи (mx_hosts на входе в check, resolver set).
- В check_email_deep: лог mx_hosts.
- Добавлен @pytest.mark.integration тест на google.com (проверяет SPF sources не пуст).
- (Дальнейшая диагностика в проде по логам: resolver, domain (registrable), mx_hosts из intel.)

## Изменённые/новые

- src/email_intel/deep_client.py (nameservers + log)
- src/tasks/check_email_deep.py (log)
- tests/unit/test_check_email_deep_task.py (integration test)
- handoff + session report

## Проверки

- pytest -k "deep" (unit + integration if net):
- ruff/mypy: ок

## Следующий

- TASK-0078 хотфикс релиз v0.15.1 (вкл. 75-77)
- Если логи покажут другую причину — доп. фикс.

## PR

(после)
