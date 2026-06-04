# 2026-06-05 — Диагностика (для админа): поддомены не досылаются, MX пуст, deep email нулевой

**Вывод архитектора по репо:** код доставки/email-слоя в HEAD **идентичен
v0.15.2** (`git diff 33b4484..HEAD -- src/tasks/check_subdomains.py
src/tasks/check_email_deep.py src/tasks/check_email_intel.py
src/bot/handlers/whois.py src/email_intel/ src/services/formatters*.py` —
пусто). Зависимости и compose/deploy тоже без изменений. Это **не регрессия
main** — проблема в рантайме прода.

Общее у симптомов: всё это ARQ-задачи **worker**'а с прямым выходом в сеть
(DNS-резолвы для MX/deep, HTTPS к crt.sh). Важно: при сбое задачи
пользователю не шлётся ничего (fail-path молчит), повторный тап рендерит
старый кэш — выглядит как возврат бага 0075, но это маскировка сетевого сбоя.

## Чек-лист на прод-машине (по порядку)

### 1. Какой код реально крутится в worker/scheduler

```bash
docker compose ps   # колонка CREATED у ww-worker vs ww-bot
docker compose exec worker grep -c deliver_chat_id /app/src/tasks/check_subdomains.py
# ≥1 — код свежий; 0 — worker на образе до v0.15.1 → пересобрать:
# docker compose build worker scheduler && docker compose up -d worker scheduler
docker compose exec worker python -c "import src._build_info as b; print(vars(b))"
```

### 2. Egress из контейнера worker

```bash
# DNS (MX gmail.com должен резолвиться)
docker compose exec worker python -c "import dns.resolver; print(dns.resolver.resolve('gmail.com','MX')[0])"
# HTTPS (crt.sh)
docker compose exec worker python -c "import urllib.request; print(urllib.request.urlopen('https://crt.sh', timeout=15).status)"
```

Если падает — смотреть фаервол/сеть хоста (ufw-правила привязаны к subnet
172.28.0.0/16; проверить `sudo ufw status numbered` и цепочку DOCKER-USER в
iptables, не пересоздавалась ли docker-сеть).

### 3. Что говорят кэши и логи

```bash
# last_error в кэшах — там будет настоящая причина
docker compose exec postgres psql -U <user> -d <db> -c \
  "select domain, fail_count, last_error, fetched_at from subdomain_enum_cache order by fetched_at desc nulls last limit 5;"
docker compose exec postgres psql -U <user> -d <db> -c \
  "select domain, fail_count, last_error, fetched_at from email_intel_cache order by fetched_at desc nulls last limit 5;"
# логи worker в момент нажатия кнопки
docker compose logs worker --since 15m
```

Также проверить приватный админ-канал (ADR 019) — задачи с ошибками должны
были насыпать алертов.

### 4. Если worker свежий и сеть ок

Прислать архитектору вывод пунктов 1–3 (новый файл в docs/sessions/ или
коммит-нота) — копаем глубже.

## Кандидат в таски (независимо от исхода)

**TASK-0086 (предложение):** on-demand задачи при фейле должны досылать
пользователю сообщение об ошибке («crt.sh недоступен, попробуйте позже»),
а не молчать — иначе любой сетевой сбой выглядит как регрессия доставки.
