# SESSION-0070 — WebApp write-действия

**Дата:** 2026-06-09 · **Таск:** TASK-0070 · **Ветка:** task/0070-webapp-write-actions
· **Исполнитель:** Grok

## Задача
Добавить write-эндпойнты в backend (/toggle, /add, /remove, /bulk, /settings, /alerts/read, /wishlist, /import) через DomainService/репо, с audit, лимитами, ownership.

Подключить во фронте: MainButton, sheets, forms, optimistic + toast + haptic, error rollback.

## Выполнено
- Backend: src/bot/webapp/api.py — write routes (toggle_notifications с ownership, add с DomainService, remove, bulk, settings, alerts read, wishlist, import stub).
- audit() на значимые.
- webhook.py — mount webapp (read+write).
- auth.py — recreated for completeness.
- Frontend: webapp/src/lib/api.ts — write helpers (toggle, add, remove, bulk, updateSettings, markAlertsRead, addWishlist).
- App.tsx — UI для writes: toggle в domain row, bulk select + action, add form, settings save, wishlist, optimistic updates, toast, MainButton states, haptic.
- Full navigation + chrome.
- Validation, PII (user scoped).

## Проверки
- Frontend `npm run build` ✅
- Ruff/mypy on backend — fixed critical (unused, from None).
- Backend writes use services/audit as required.
- Optimistic + rollback on error.

## Что осталось
- Полные тесты pytest для writes (unit on api handlers).
- Реальный TG тест (добавить, тоггл, bulk, settings).
- Импорт CSV полная (csv_io + preview).
- Facade wiring for add may need real whois proxy in prod.
- 0071 audit security.

## PR
https://github.com/nmetluk/whois-watcher/pull/48

Per handoff.
