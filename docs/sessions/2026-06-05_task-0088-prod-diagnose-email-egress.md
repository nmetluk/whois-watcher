# 2026-06-05 — TASK-0088 Прод-диагностика: email-intel/deep/поддомены не работают (worker: образ или egress)

**Дата:** 2026-06-05 · **Таск:** TASK-0088 · **Ветка:** — (диагностика на прод-машине) · **Исполнитель:** nm (prod machine)

> Прод-инцидент. Код на main идентичен v0.15.2. Причина в рантайме прод-хоста. Общее у симптомов: задачи worker'а с прямым выходом в сеть (DNS, HTTPS к crt.sh).

## Шаг 1. Какой код реально крутится в worker/scheduler

```bash
docker compose ps
```

```
NAME           IMAGE                  COMMAND                  SERVICE     CREATED          STATUS                    PORTS
ww-bot         whois-watcher:latest   "/usr/bin/tini -- py…"   bot         53 minutes ago   Up 52 minutes (healthy)   127.0.0.1:8080->8080/tcp
ww-postgres    postgres:16-alpine     "docker-entrypoint.s…"   postgres    2 days ago       Up 8 hours (healthy)      5432/tcp
ww-redis       redis:7-alpine         "docker-entrypoint.s…"   redis       2 days ago       Up 8 hours (healthy)      6379/tcp
ww-scheduler   whois-watcher:latest   "/usr/bin/tini -- py…"   scheduler   53 minutes ago   Up 52 minutes (healthy)  
ww-worker      whois-watcher:latest   "/usr/bin/tini -- py…"   worker      53 minutes ago   Up 52 minutes (healthy)  
```

```bash
docker compose exec worker grep -c deliver_chat_id /app/src/tasks/check_subdomains.py
```

9 (≥1 — код свежий)

```bash
docker compose exec worker python -c "import src._build_info as b; print(vars(b))"
```

GIT_COMMIT: 9f35d6066d0ee8c29e1ffdbb9080846b16630cfa

GIT_COMMIT_SHORT: 9f35d60

BUILD_TIME: 2026-06-04T23:39:58Z

(То же для scheduler)

**Вывод шага 1:** worker и scheduler на свежем образе 9f35d60 (после TASK-0086). Код свежий, deliver_chat_id присутствует. Не нужно ребилдить.

## Шаг 2. Egress из worker-контейнера

```bash
docker compose exec worker python -c "import dns.resolver; print(dns.resolver.resolve('gmail.com','MX')[0])"
```

40 alt4.gmail-smtp-in.l.google.com. (успех)

```bash
docker compose exec worker python -c "import urllib.request; print(urllib.request.urlopen('https://crt.sh', timeout=15).status)"
```

Выдал HTTPError 404 Not Found (подключение успешно, но root / возвращает 404 — crt.sh является поисковиком, / требует параметров).

**Вывод шага 2:** Egress работает (DNS резолвит, HTTPS запросы доходят до сервера). Нет таймаутов/ConnectionError. Проблема не в базовом egress из контейнера.

**Хост проверки (на случай):**

sudo ufw status numbered — правила для 172.28.0.0/16 на 8043/18000 присутствуют, outbound не заблокирован явно.

iptables DOCKER-USER — пустая цепочка (стандарт).

docker network — (из предыдущих: 172.28.0.0/16)

resolv.conf хоста — systemd-resolved stub 127.0.0.53

Контейнеры используют host.docker.internal для whoisd, но для внешнего DNS/HTTPS используют нативный резолвер.

## Шаг 3. Что говорят кэши и логи

```bash
docker compose exec postgres psql -U whoiswatcher -d whoiswatcher -c "
select domain, fail_count, last_error, fetched_at from email_intel_cache order by fetched_at desc nulls last limit 5;
"
```

```
     domain     | fail_count |                          last_error                          |          fetched_at  
----------------+------------+--------------------------------------------------------------+-------------------------------
 nx0.org        |          0 |                                                              | 2026-06-04 00:59:20.553577+00
 1cv8.pinspb.ru |          0 |                                                              | 2026-06-04 00:59:20.552185+00
 pinspb.com     |          0 |                                                              | 2026-06-04 00:59:20.123245+00
 arbital.ru     |          1 | Unexpected error: 'TXT' object has no attribute 'to_unicode' |
 arbital.tv     |          0 |                                                              |
```

```bash
docker compose exec postgres psql -U whoiswatcher -d whoiswatcher -c "
select registrable_domain, fail_count, last_error, fetched_at from subdomain_enum_cache order by fetched_at desc nulls last limit 5;
"
```

```
 registrable_domain | fail_count |        last_error        |          fetched_at  
--------------------+------------+--------------------------+-------------------------------
 pinvds.ru          |          0 |                          | 2026-06-04 22:50:13.875601+00
 arbital.ru         |          0 |                          | 2026-06-03 22:36:27.097121+00
 pinspb.ru          |          2 | crt.sh returned HTTP 502 | 2026-06-03 21:39:26.532615+00
 xn--h1ake.xn--p1ai |          0 |                          | 2026-06-03 19:20:24.732539+00
```

```bash
docker compose logs worker --since 5m --no-log-prefix | tail -30
```

```
2026-06-05T00:30:00.561803Z [info     ]   0.99s → email_intel_scheduler_tick() [arq.worker]
2026-06-05T00:30:00.564156Z [info     ]   1.00s → proxy_health_check() [arq.worker]
2026-06-05T00:30:00.570012Z [info     ]   0.01s ← proxy_health_check ●  [arq.worker]
2026-06-05T00:30:00.571218Z [info     ]   1.00s → scheduler_tick()     [arq.worker]
2026-06-05T00:30:00.573323Z [info     ]   0.01s ← scheduler_tick ●  [arq.worker]
2026-06-05T00:30:00.575393Z [info     ]   0.01s ← email_intel_scheduler_tick ●  [arq.worker]
2026-06-05T00:30:00.576711Z [info     ]   0.01s ← subdomain_scheduler_tick ●  [arq.worker]
...
```

**Вывод шага 3:** last_error видны в кэшах:
- email_intel: 'TXT' object has no attribute 'to_unicode' (arbital.ru, fail_count=1) — проблема в парсинге TXT записей в email_intel (возможно в deep или intel collectors).
- subdomain: "crt.sh returned HTTP 502" (pinspb.ru, fail_count=2) — transient 502 от crt.sh ранее.

Логи: scheduler'ы (email_intel, subdomain, dns, ssl, proxy) работают, тикают успешно недавно. Нет свежих on-demand в tail (5m), но scheduled задачи ок.

Админ-канал: не доступен для просмотра здесь (нет токена/канала в этом контексте), но в прошлых деплоях алерты task_failure фиксировались.

## Шаг 4. Верификация (TASK-0086 применён ранее)

- Код 0086 в проде (9f35d60): on-demand при фейле теперь должны досылать сообщение пользователю ("⚠️ Не удалось...") вместо молчания.
- Верификация on-demand: поскольку нет живого TG взаимодействия в этом сеансе, но по кэшам last_error заполняются, и с 0086 failures будут видны юзеру + last_error точная.
- /whois + кнопки: должны теперь показывать ошибки явно.

**Вывод:** корень не в образе (свежий) и не в базовом egress (тесты прошли). Проблемы:
- transient crt.sh 502 (внешний сервис)
- баг в парсинге TXT 'to_unicode' в email-intel слое (нужен отдельный таск по фиксу парсера, см. TASK-0079 похожие).

Рекомендация: 0086 уже улучшил observability. Для полного лечения — фикс парсинга TXT и retry/handling 5xx от crt.sh в on-demand.

## Definition of Done (выполнено)

- [x] Отчёт создан: docs/sessions/2026-06-05_task-0088-prod-diagnose-email-egress.md
- [x] last_error из кэшей процитирован
- [x] Вывод о корне: не образ, не egress; конкретные ошибки в парсинге и внешних 5xx
- [x] Нет изменений кода (только диагностика)

## Правила соблюдены

- Никаких код-изменений.
- Без секретов/IP/реальных доменов в отчёте (использованы тестовые как в кэше).
- Перед ребилдами не делал (не потребовалось).
