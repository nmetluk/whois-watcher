---
id: TASK-0088
title: 🔴 Прод-диагностика — email-intel/deep/поддомены не работают (worker: образ или egress)
status: open
milestone: v0.16.1
adr: 040
area: infra
depends_on: []
branch: — (диагностика на прод-машине; в git идёт только отчёт)
owner: —
session: docs/sessions/<дата>_task-0088-prod-diagnose-email-egress.md
pr: —
created: 2026-06-05
---

# TASK-0088 — Прод-диагностика: MX/deep email пустые, поддомены не приходят

> 🔴 Прод-инцидент. Код на main **идентичен v0.15.2** (где всё работало) —
> `git diff 33b4484..HEAD` по `src/tasks/check_{subdomains,email_deep,email_intel}.py`,
> `src/email_intel/`, `src/bot/handlers/whois.py`, форматтерам — **пуст**.
> Зависимости и compose тоже. Значит, причина в рантайме прод-хоста.
> Общее у симптомов: всё это задачи **worker'а с прямым выходом в сеть**
> (DNS-резолвы для MX/SPF/DKIM/DMARC и deep, HTTPS к crt.sh).
> Контекст: `docs/sessions/2026-06-05_diagnosis-ondemand-email-prod.md`.

## Что сделать (по порядку, результаты каждого шага — в отчёт)

### Шаг 1. Какой код реально крутится в worker/scheduler

```bash
docker compose ps
# в отчёт: CREATED и образ у ww-worker / ww-scheduler vs ww-bot

docker compose exec worker grep -c deliver_chat_id /app/src/tasks/check_subdomains.py
# ≥1 — код свежий; 0 — worker на образе до v0.15.1 → СТОП, корень найден:
#   docker compose build worker scheduler && docker compose up -d worker scheduler
#   и повторить ручной тест в Telegram

docker compose exec worker python -c "import src._build_info as b; print(vars(b))"
# в отчёт: commit/версия из build info
```

### Шаг 2. Egress из worker-контейнера (если шаг 1 показал свежий код)

```bash
# DNS: MX gmail.com обязан резолвиться
docker compose exec worker python -c "import dns.resolver; print(dns.resolver.resolve('gmail.com','MX')[0])"

# HTTPS: crt.sh
docker compose exec worker python -c "import urllib.request; print(urllib.request.urlopen('https://crt.sh', timeout=15).status)"
```

Оба упали / таймаут → egress сломан. Дальше смотреть хост:

```bash
sudo ufw status numbered          # правила для 172.28.0.0/16 на месте?
sudo iptables -L DOCKER-USER -n -v
docker network inspect $(docker network ls -q --filter name=whois) | grep -i subnet
# subnet должен быть 172.28.0.0/16 (зафиксирован в docker-compose.yml)
cat /etc/resolv.conf              # и резолвер хоста жив?
```

### Шаг 3. Что говорят кэши и логи (выполнить в любом случае)

```bash
# Настоящая причина записана в last_error:
docker compose exec postgres psql -U <user> -d <db> -c \
  "select domain, fail_count, last_error, fetched_at from email_intel_cache order by fetched_at desc nulls last limit 5;"
docker compose exec postgres psql -U <user> -d <db> -c \
  "select registrable_domain, fail_count, last_error, fetched_at from subdomain_enum_cache order by fetched_at desc nulls last limit 5;"

# Нажать в Telegram кнопку «Глубокий e-mail» на любом домене и снять логи:
docker compose logs worker --since 5m
```

Также: проверить приватный админ-канал (ADR 019) — алерты `task_failure`
за последние дни; в отчёт — типы и количество (без чувствительного).

### Шаг 4. Если применён фикс — верификация

- В Telegram: кнопка «Поддомены» → список приходит БЕЗ второго нажатия
  (после деплоя TASK-0086 при фейле должно прийти «⚠️ Не удалось…» —
  тишина теперь сама по себе баг).
- `/whois` любого домена с почтой → MX отображается.
- «Глубокий e-mail» → непустой отчёт.

## Definition of Done

- [ ] Отчёт `docs/sessions/<дата>_task-0088-prod-diagnose-email-egress.md`
      по шаблону: вывод каждого шага (без секретов, токенов, реальных
      пользовательских доменов — свои тестовые ок), вывод о корне,
      применённый фикс (если был), результат верификации шага 4
- [ ] `last_error` из обеих таблиц процитирован в отчёте (это главное)
- [ ] Если менялась конфигурация хоста (ufw/доker-сеть) — зафиксировать
      что именно, и предложить дополнение в `docs/deployment.md`
- [ ] `python scripts/handoff.py done TASK-0088` + push отчёта в main

## Правила

- Никаких изменений кода в этом таске — только диагностика, рестарты,
  ребилды и конфигурация хоста. Если выяснится, что нужен код-фикс —
  написать в отчёте «нужен TASK-NNNN» с описанием, архитектор заведёт.
- Не логировать в отчёт IP сервера (правило CLAUDE.md), секреты, токены.
- Перед любыми ребилдами БД не трогать; `docker compose down -v` — запрещён.
