---
id: TASK-0096
title: 🟡 whois-proxy — upstream хостовых патчей 0095 (TTL_NEG=60, RDAP-404, BIND_ADDR_WHOIS)
status: open
milestone: v0.17.0
adr: 046
area: infra
depends_on: [TASK-0095]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-06
---

# TASK-0096 — upstream хостовых патчей 0095 в репо whois-proxy

> Контекст: этот файл, отчёт 0095
> (`docs/sessions/2026-06-06_task-0095-whoisd-relay-negative-ttl-60.md`),
> репозиторий **nmetluk/whois-proxy**, ww.txt на хосте.

## Цель

`/opt/whoisd/server.py` и systemd-юниты на обоих хостах (прод + VDS)
снова собираются из git whois-proxy один в один. Невыполненный DoD-пункт
TASK-0095: хостовые правки (TTL_NEG=60, `rdap_lookup` → `(data, is_404)`,
RDAP-404 как no-data, `BIND_ADDR_WHOIS`) сделаны напрямую на хостах,
HEAD whois-proxy остался `2ae4442` — повторение дрейфа, который закрывал
TASK-0093/коммит `666af2a`.

## Что сделать

- Снять текущие `/opt/whoisd/server.py` (+ юниты) с прод-хоста и VDS,
  diff с whois-proxy HEAD `2ae4442`.
- Закоммитить расхождения в whois-proxy (оба варианта server.py:
  main/proxy и edge/relay; дефолты `RU_UPSTREAM_TTL_NEG=60`,
  `CACHE_TTL_NEG=60`, `NO_DATA_TTL=60`; RDAP-404 ветка; `BIND_ADDR_WHOIS`;
  актуальные systemd-юниты как примеры/шаблоны).
- Перекатить хосты ИЗ git (а не наоборот) и убедиться, что байт-в-байт:
  `sha256sum /opt/whoisd/server.py` == файла из репо; whoisd active,
  негативы ttl ≤60, позитивы 24h (инварианты 0095).

## Definition of Done

- [ ] whois-proxy HEAD содержит все хостовые правки 0095; на хостах —
      файлы из git (хэши совпадают)
- [ ] whoisd на обоих хостах active, инварианты 0095 перепроверены
- [ ] Per-session отчёт в `docs/sessions/` (без IP/SSH-деталей!),
      `handoff.py validate`

## Ссылки

- TASK-0095 (исходные правки), TASK-0093 + `666af2a` (урок «хостовые
  патчи — только версионированные»), ADR 046, ADR 011 (whois-proxy)
