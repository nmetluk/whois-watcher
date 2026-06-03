---
id: TASK-0077
title: 🔴 Диагностика+фикс — глубокий e-mail всегда пустой
status: done
milestone: v0.15.1
adr: 040
area: code
depends_on: []
branch: task/0077-fix-deep-email-empty
owner: grok-4.3
session: docs/sessions/2026-06-09_task-0077-fix-deep-email-empty.md
pr: https://github.com/nmetluk/whois-watcher/pull/52
created: 2026-06-09
---

# TASK-0077 — Глубокий e-mail возвращает пусто (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🔴 Прод-баг (фидбек #4: «анализ глубокой почты не работает, всегда пусто»).

## Симптом

`format_email_deep` всегда показывает пустые секции — «ни разу не получили
значений кроме пустых». Отдельно от доставки (TASK-0075): даже на повторном
нажатии (кэш свежий) разбор пуст.

## Гипотезы (проверить)

1. **Коллекторы возвращают пусто.** `fetch_deep_email` собирает SPF/MTA-STS/
   TLS-RPT/BIMI/DANE через `dns.asyncresolver.Resolver()` (default-конфиг) +
   `aiohttp`. Если в контейнере воркера/scheduler resolver не настроен/не
   резолвит — все ветки молча → None (есть `except → None`), результат
   «reachable, но пусто». (NB: основной DNS у бота работает — но проверить
   именно этот resolver: nameservers, `/etc/resolv.conf`, таймауты.)
2. **mx_hosts пуст** (если `email_intel_cache` не наполнен) → DANE всегда пуст
   (но SPF/MTA-STS/BIMI должны работать независимо).
3. **Домен передаётся не тот** (apex vs registrable vs поддомен) — записи на
   apex, а зовём не то.
4. **Тестировали домены без deep-записей** (у большинства нет MTA-STS/DANE/BIMI;
   но SPF почти у всех есть) — тогда это **не баг**, а ожидаемо; но SPF-источники
   должны быть непустыми.

## Что сделать

- **Интеграционный тест** против известного «богатого» домена (напр.
  `google.com`): ждём непустой SPF (sources/lookup_count), MTA-STS mode, DMARC.
  Гонять как `@pytest.mark.integration` (реальный DNS/HTTP в CI — есть сервисы,
  но нужен внешний DNS/сеть; либо отдельный opt-in-маркер). Если тест **красный**
  на google.com → подтверждён баг (resolver/проводка) → чинить.
- Добавить **диагностические логи** в `check_email_deep`/`fetch_deep_email`
  (сколько sources/секций собрано, какие ветки упали) — чтобы видеть в проде.
- Проверить, какой `domain` приходит в `check_email_deep` (registrable?) и что
  `mx_hosts` берётся корректно (зависит от `email_intel_cache`).
- Починить найденную причину (вероятно — DNS-resolver в контейнере или
  передача домена).

## Definition of Done

- [ ] Интеграц-тест на `google.com` зелёный (deep-разбор непустой)
- [ ] Найденная причина устранена; диаг-логи добавлены
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Реальная проверка в Telegram на домене с SPF/MTA-STS/DMARC
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 040; `src/email_intel/deep_client.py` (`fetch_deep_email`),
  `src/tasks/check_email_deep.py`, `src/services/formatters.py` (`format_email_deep`).
