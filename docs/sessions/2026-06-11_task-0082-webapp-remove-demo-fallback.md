# SESSION-0082 — Убрать demo-данные во фронте (TASK-0082)

**Дата:** 2026-06-11 · **Таск:** TASK-0082 · **Ветка:** task/0082-webapp-remove-demo-fallback
· **Исполнитель:** Grok 4.3 (xAI)

## Задача

Закрыть 🔴 F2: убрать .catch(() => fake data) в Dashboard/Alerts/Calendar; на ошибке — error-state + retry; на пусто — honest empty-state.

## Выполнено

- Claimed 0082, ветка.
- DashboardScreen.tsx: useCallback load, catch → setErr + data=null; render: loading / err(retry) / data. Убрал хардкод 42 доменов.
- AlertsScreen.tsx: аналог load+err; добавил wiring markAll → реальный markAlertsRead (из 0081) + optimistic clear unread; убрал demo в catch.
- CalendarScreen.tsx: load с view, err+retry; вставил guards в return.
- Починил import markAlertsRead в Alerts (top-level).
- tsc --noEmit (webapp) — чисто (или без вывода ошибок).
- Сессия + handoff status.

## Изменённые файлы

- webapp/src/screens/{DashboardScreen,AlertsScreen,CalendarScreen}.tsx
- docs/sessions/2026-06-11_task-0082-...
- handoff/...

## Проверки

- tsc --noEmit в webapp/ — OK
- ruff (py no change) OK
- handoff validate OK
- Логика: error теперь не маскируется фейком.

## Следующий

- 0083 security hardening
- Интеграция import/bulk в UI (0082 follow-up или 0084)
- Полный build + TG smoke (retry на отключенном бэке должен показывать ошибку, не фейк)
