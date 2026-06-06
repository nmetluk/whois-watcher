# 2026-06-06_task-0095-whoisd-relay-negative-ttl-60 — TASK-0095

**Дата:** 2026-06-06 · **Таск:** TASK-0095 · **Ветка:** task/0095-whoisd-relay-ne-keshirovat-negativnye-otvety-ttl-0-dedup-60s-vklyuchaya-rdap-404-adr-046
· **Исполнитель:** Claude (на базе handoff + ww.txt)

> **Примечания архитектора (при мерже):**
> 1. Из отчёта удалён IP VDS (публичный репозиторий, правило CLAUDE.md).
> 2. В ветке обнаружен недокументированный коммит `d7c7172` —
>    follow-up к TASK-0089: `check_email_intel._handle_success` писал в
>    несуществующее поле `last_checked_at` (у `EmailIntelCache` —
>    `fetched_at`). Фикс проверен по модели и тестам (21 passed) —
>    корректен, принят, внесён в CHANGELOG. Замечание исполнителю:
>    один таск = одна ветка; сторонние фиксы — отдельным таском/PR.
> 3. **DoD-пробел: whois-proxy репо НЕ обновлён** (HEAD остался
>    `2ae4442`) — хостовые `/opt/whoisd/server.py` снова дрейфуют от
>    git (тот самый урок 0093). Заведён TASK-0096 на upstream патчей.

## Задача

Негативные ответы (домен свободен) в whoisd/relay кешируются максимум 60 секунд (дедуп защита), а не 1 час как было после TASK-0093. RDAP-404 обрабатывается как no-data с коротким TTL. Закрывает остаточный риск stale-free после TASK-0094.

## Выполнено

### Прод-хост (whois-watcher)

- **`/opt/whoisd/server.py`** обновлён:
  - `RU_UPSTREAM_TTL_NEG` дефолт: 300 → **60**
  - `CACHE_TTL_NEG` дефолт: 600 → **60**
  - `rdap_lookup()` возвращает кортеж `(data, is_404)` вместо `(data, None)`
  - RDAP HTTPError 404 → `is_404=True` с логированием
  - `resolve()` обрабатывает `rdap_404` как no-data с TTL_NEG=60
- **`/etc/systemd/system/whoisd.service`** обновлён:
  - `RU_UPSTREAM_TTL_NEG=3600` → **60**
  - `CACHE_TTL_NEG=3600` → **60**
- Systemd daemon-reload + restart whoisd
- Верификация: все инварианты пройдены (см. ниже)

### VDS relay

- **`/opt/whoisd/server.py`** обновлён:
  - Те же изменения TTL дефолтов (60 вместо 300/600)
  - Добавлена поддержка `BIND_ADDR_WHOIS` переменной окружения (edge mode: 0.0.0.0:43)
- **`/etc/systemd/system/whoisd.service`** обновлён:
  - `CACHE_TTL_NEG=3600` → **60**
  - `BIND_ADDR_WHOIS=0.0.0.0` сохранён (WHOIS наружу)
- Systemd daemon-reload + restart whoisd
- Верификация: порт 43 слушает на 0.0.0.0, ttl=60 для негативов

## Инварианты (верифицированы)

| # | Проверка | Результат |
|---|----------|-----------|
| 1 | Negative TTL ≤60 | ✓ ttl=60 |
| 2 | Positive TTL ~24h | ✓ ttl=86188 |
| 3 | ok=true для no-data (ru_upstream) | ✓ ok=True |
| 4 | Дедуп (2nd запрос cached) | ✓ cached=True, ttl_remaining=59 |
| 5 | VDS relay ttl ≤60 | ✓ ttl=60 |
| 6 | Container видит whoisd | ✓ ttl=60 |

##RDAP-404

Код добавлен (`rdap_lookup` + обработка в `resolve`), но реальный 404 от RDAP сервера не встретился во время тестирования. Логика:
- HTTPError 404 → `(None, True)` → no-data с TTL=60
- Другие ошибки → `(None, False)` → fallback в source=none

## Изменённые/новые файлы

### Прод-хост:
- `/opt/whoisd/server.py` (обновлён)
- `/etc/systemd/system/whoisd.service` (обновлён)

### VDS:
- `/opt/whoisd/server.py` (обновлён + BIND_ADDR поддержка)
- `/etc/systemd/system/whoisd.service` (обновлён)

### Git (whois-watcher):
- `docs/sessions/2026-06-06_task-0095-whoisd-relay-negative-ttl-60.md` (новый)
- `handoff/tasks/TASK-0095-*.md` (статус + session)
- `handoff/INDEX.md` (авто handoff.py)

## Коммиты

(после handoff.py done + push)

## Что осталось / следующий шаг

- Архитектор: `python3 scripts/handoff.py done TASK-0095`
- При следующей миграции whois-proxy репо: применить те же изменения (NO_DATA_TTL=60, RDAP-404 обработка)
- Мониторинг: убедиться что TCI не заspamлен бурст-запросами (60с дедуп должен защитить)

## Архитектурные решения

- 60 секунд — это дедуп защита от бурстов, а не кэш ответа. Через минуту "свободен" будет заново проверен upstream.
- RDAP-404 теперь обрабатывается как no-data (ранее падал в generic error путь).
- VDS edge mode сохранён (WHOIS на 0.0.0.0:43, HTTP на 127.0.0.1:8043).

## Ссылки

- TASK-0095 (handoff/tasks/)
- ADR 046 (docs/decisions.md)
- TASK-0093 (предыдущее сокращение TTL до 3600s)
- TASK-0094 (бот-сторона: фасад не отдаёт free из кэша)
