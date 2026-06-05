# 2026-06-07 — TASK-0092: «свободен» только после RDAP-верификации (ADR 045)

**Контекст.** Отчёт TASK-0091 (исполнитель, образцовый) дал улики по
инциденту discozavr.ru: proxy отдавал легитимный «No entries found» от
TCI/relay для уже зарегистрированного домена; парсер послушно вернул
`is_registered=False`. Бот 2+ суток показывал «свободен». Выполнено
архитектором напрямую в main.

## Решение (ADR 045)

**Positive evidence бьёт negative.** «Нет записи в WHOIS-тексте» — слабое
свидетельство свободности (лаг публикации, кэш relay, сбой). Запись в
RDAP — сильное свидетельство занятости.

1. `lookup_domain` → `_verify_unregistered`: «свободен» из текстовых
   источников (`whois`, `proxy_whois`, `proxy_whois_ru`, `proxy_none`)
   перепроверяется независимым RDAP-запросом (whoisit, IANA bootstrap —
   мимо relay и proxy):
   - RDAP found+registered → возвращаем данные RDAP (домен ЗАНЯТ),
     `raw_data.free_contradicted_whois_source` + warning в лог;
   - RDAP not_found → `free_verified="rdap"`;
   - RDAP error/unsupported → `free_unverified=True`.
   RDAP-источники (`rdap`, `proxy_rdap`) не перепроверяются.
2. «Сбой ≠ свободен»: `looks_like_upstream_error` (рейтлимит TCI, HTML,
   502/504, quota...) → `WhoisError(unavailable)` в proxy_client и в
   direct WHOIS:43 — до парсинга.
3. UX: `free_unverified` → «записи в WHOIS не найдено… подтвердить по
   второму источнику не удалось» вместо уверенного «свободен» (ru/en).

Без миграций: флаги в `raw_data` (JSONB кэша).

## Верификация

- `tests/unit/test_free_verification.py` — 16 тестов: кейс инцидента
  (WHOIS free + RDAP registered → ЗАНЯТ), подтверждение 404, маркировка
  при недоступном RDAP, скипы (registered / rdap-источник / WhoisError —
  RDAP не дёргается), free-детекция на **реальном тексте TCI из отчёта
  0091** + 5 ошибочных текстов + реальный REGISTERED-ответ, рендер
  обоих шаблонов через реальный `t()`.
- Смежные: whois/proxy/parser/wishlist — 267 passed. ruff/black чисто.

## Эффект на инцидент

После деплоя `/check discozavr.ru`: WHOIS-текст скажет «No entries» →
RDAP-кросс-чек увидит регистрацию → бот покажет ЗАНЯТ с данными RDAP.
Если RDAP TCI недоступен с IP бота — честное «подтвердить не удалось»
вместо ложного «свободен» (и это сигнал в TASK-0093).

## Хвосты

- TASK-0093 (открыт, инфра): relay/VDS — почему «No entries» жил 2 суток;
  отдельный короткий TTL негативных ответов в relay и proxy.
- Real-world: /check discozavr.ru после деплоя (DoD).
- mypy локально не прогнан (sandbox 3.10) — CI.
