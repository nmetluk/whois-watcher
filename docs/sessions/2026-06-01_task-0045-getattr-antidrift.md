# SESSION-0045 — Anti-drift: убрать getattr на SubdomainEnumCache (TASK-0045)

**Дата:** 2026-06-01  
**Таск:** TASK-0045  
**Ветка:** task/0045-subdomains-button-getattr-antidrift  
**PR:** (будет)  
**Исполнитель:** Claude (Grok)

---

## Цель

Убрать `getattr(orm_object, "field", default)` из freshness-логики кнопки «Поддомены» (TASK-0042), в соответствии с правилом CLAUDE.md «Защита от рассинхрона».

## Что было неправильно

В коде после PR #31 использовался `getattr`:
- `_is_subdomain_cache_fresh(cached: Any)`
- `getattr(cached, "subdomains", None)`
- `getattr(cached, "fetched_at", None)`

Это маскирует дрейф: если поле в модели `SubdomainEnumCache` переименуют — код тихо начнёт всегда считать кэш несвежим и постоянно пере-enqueue'ить задачи.

## План

1. Типизировать `_is_subdomain_cache_fresh(cached: SubdomainEnumCache | None)`
2. Заменить все `getattr` на прямой доступ `cached.xxx` с явными None-проверками.
3. В тестах:
   - Удалить `test_uses_getattr_defensively`
   - Использовать `MagicMock(spec=SubdomainEnumCache)` вместо голого мока.
4. Убедиться, что mypy доволен прямым доступом.

## Статус

Начало работы. Следующий шаг — правка `src/bot/handlers/whois.py`.
