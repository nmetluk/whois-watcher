---
date: 2026-05-30
task: TASK-0019
title: Instance-тег в сообщениях админ-канала
author: claude
---

# TASK-0019: Instance-тег в сообщениях админ-канала (ADR 019)

## Цель

Каждое сообщение в админ-канал (ADR 019) начинается с идентификатора
инстанса: **label + домен + server IP** — чтобы при развёртывании на разных
машинах было видно, откуда сообщение.

## Выполнено

### Конфигурация

- **`src/config/settings.py`** — новые поля:
  - `instance_name: str` (default `""`) — метка деплоя
  - `server_ip: str` (default `""`) — публичный IP
  - `instance_domain` — computed_field, извлекает домен из `webhook_base_url`

### AlertService

- **`src/services/alerts.py`**:
  - Функция `instance_tag(settings) -> str` — собирает тег из непустых частей
  - Обновление `_send` — передача тега в `_format_alert`
  - Обновление `_format_alert` — добавление тега в начало сообщения

### Конфигурация окружения

- **`.env.example`** — добавлены `INSTANCE_NAME` и `SERVER_IP` с комментариями

### Документация

- **`CLAUDE.md`** — уточнение правила про runtime IP:
  - НЕ логировать в structlog
  - Допускается в приватном админ-канале через явный конфиг `SERVER_IP`

### Тесты

- **`tests/unit/test_alert_service.py`** — расширение:
  - `TestInstanceTag` — 5 новых тестов:
    - `test_instance_tag_collects_all_parts` — все части
    - `test_instance_tag_skips_empty_parts` — пропускает пустые
    - `test_instance_tag_empty_when_all_empty` — пустой когда все пусты
    - `test_instance_tag_name_only` — только имя
    - `test_format_alert_includes_tag_when_provided` — тег в сообщении
    - `test_format_alert_no_tag_when_empty` — нет тега когда пустой
  - `TestAlertService::test_send_with_instance_tag` — интеграционный тест

## Инварианты (защищены тестами)

- ✅ Каждое отправленное admin-сообщение начинается с `[<tag>]`, когда хоть одна
  из частей задана
- ✅ Если `instance_name`/`server_ip` пусты и домен недоступен — тег пуст,
  сообщение уходит без префикса
- ✅ Дедупликация (`_dedup_key`) не зависит от тега (поведение не меняется)
- ✅ IP не утекает в structlog-логи (только в админ-канал)
- ✅ Устойчивость к MagicMock в тестах (проверка типа str)

## Сложности

1. **MagicMock в тестах**: `getattr(settings, "instance_name", "")` возвращает
   MagicMock (а не `""`), потому что мок автоматически создаёт атрибуты.
   Решено: добавлена проверка `isinstance(name, str)` и `or ""`.

## Проверки

- ✅ `pytest tests/unit/` — 803 passed
- ✅ `ruff check src/...` — все проверки пройдены
- ✅ `mypy src/...` — Success: no issues found
- ✅ pre-commit hooks — passed

## Формат тега

```
[prod-admin · whois.example.com · 5.188.88.78]
🚨 #critical
title

details
```

При пустых частях:
```
[whois.example.com]
ℹ️ #info
worker started
```

При всех пустых — обычный формат без префикса.

## Что НЕ делалось (out of scope)

- (Опц.) приписка в ADR 036 — не требуется, изменения в ADR 019 минимальны

## Файлы изменены

- `src/config/settings.py` — instance_name, server_ip, instance_domain
- `src/services/alerts.py` — instance_tag, _send, _format_alert
- `.env.example` — INSTANCE_NAME, SERVER_IP
- `CLAUDE.md` — уточнение правила про IP
- `tests/unit/test_alert_service.py` — тесты
- `handoff/tasks/TASK-0019-admin-alert-instance-tag.md` — статус done

## Following steps

- PR на merged main
