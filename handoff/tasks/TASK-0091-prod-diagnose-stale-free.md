---
id: TASK-0091
title: 🔴 Прод-диагностика — зарегистрированный домен 2 суток показывается «свободен» (discozavr.ru)
status: open
milestone: v0.16.1
adr: 028
area: infra
depends_on: []
branch: — (диагностика; в git идёт только отчёт)
owner: —
session: docs/sessions/<дата>_task-0091-prod-diagnose-stale-free.md
pr: —
created: 2026-06-07
---

# TASK-0091 — «Свободен» спустя 2 суток после регистрации

> Ручной тест: discozavr.ru был свободен (бот прав) → домен зарегистрировали
> → все внешние сервисы видят регистрацию, бот спустя 2 суток — «свободен».
> Кэш бота свежий 6ч, кэш proxy 24ч — оба истекли, live-запрос шёл и
> возвращал что-то, что парсер счёл «свободен».
>
> **Главная гипотеза (архитектор):** `_looks_like_not_found` в
> `src/whois/parser.py` матчит подстроки («not found», «no information
> available»…) по всему тексту. Если RU-relay/proxy на сбое отдаёт текст
> ошибки/HTML/рейтлимит TCI — это трактуется как «домен свободен»
> (класс «сбой ≠ свободен», ср. TASK-0079). Улика — в `raw_data` кэша.

## Шаги (вывод каждого — в отчёт)

### 1. Что видел парсер (решающее)

```bash
docker compose exec postgres psql -U whoiswatcher -d whoiswatcher -c \
  "select domain, is_registered, fetched_at, next_check_at, fail_count, last_error from whois_cache where domain='discozavr.ru';"
# и ГЛАВНОЕ — сырой текст, который сматчился как «свободен»:
docker compose exec postgres psql -U whoiswatcher -d whoiswatcher -t -c \
  "select raw_data from whois_cache where domain='discozavr.ru';" > /tmp/discozavr_raw.json
head -c 3000 /tmp/discozavr_raw.json
# Полный raw_data приложить к отчёту (секретов там нет — публичный WHOIS).
```

### 2. Что отвечает proxy прямо сейчас

```bash
curl -s "http://127.0.0.1:8043/whois?domain=discozavr.ru" | head -c 2000
# в отчёт: весь ответ; отметить поля cached/fetched_at/ttl_remaining
# Повторить два раза с интервалом ~1 мин — меняется ли (кэш живой?)
```

### 3. Что отвечает RU-relay напрямую (с прод-хоста или с VDS)

```bash
# с хоста (если relay-порт доступен) или зайти на VDS:
whois -h whois.tcinet.ru discozavr.ru | head -30
# ожидаем: domain, state: REGISTERED..., created, paid-till
```

### 4. Реакция бота при живом запросе

В Telegram: `/check discozavr.ru` (форс), затем `/whois discozavr.ru`.
Снять логи: `docker compose logs worker bot --since 5m | grep -i discozavr`.

## Definition of Done

- [ ] Отчёт в docs/sessions/ с raw_data (п.1), ответом proxy (п.2),
      ответом tcinet (п.3) и результатом /check (п.4)
- [ ] Вывод: где именно родился «свободен» — relay / proxy / парсер
- [ ] Никаких код-фиксов в этом таске: если подтверждается гипотеза
      про парсер — архитектор заведёт TASK-0092 (ужесточение
      free-детекции: «сбой ≠ свободен», точные паттерны по зонам)
- [ ] `handoff.py done TASK-0091` + push

## Правила

- Без секретов/IP в отчёте. raw_data WHOIS — публичные данные, ок.
- БД не менять (только select). Прод не рестартовать — только чтение.
