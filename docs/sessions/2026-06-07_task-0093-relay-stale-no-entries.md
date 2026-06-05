# 2026-06-07_task-0093-relay-stale-no-entries — TASK-0093 (RU-relay/VDS)

**Дата:** 2026-06-07 · **Таск:** TASK-0093 · **Ветка:** task/0093-relay-stale-no-entries
· **Исполнитель:** Grok (на базе handoff + ww.txt)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты (кроме публичных whois-ответов).

> **Примечание архитектора:** из отчёта при мерже удалены IP/SSH/имя ключа
> (публичный репозиторий, правило CLAUDE.md). Операторские детали — в ww.txt на хосте.

## Задача

Из TASK-0091: TCI (через VDS-relay) вернул «No entries found...» для discozavr.ru ~за 13 мин до реальной регистрации (22:28 vs 22:41). whoisd (и на VDS, и на прод-хосте) закешировал ответ как ok=true + 24h TTL (whois_valid/is_useful считает текст полезным). Прод-прокси отдавал stale «свободен» даже после. 0092 защитил бота RDAP-верификацией, но первоисточник (кэши relay/proxy) надо укоротить для негативных ответов.

## Выполнено

- SSH на VDS (SSH-доступ по deploy-ключу — детали в ww.txt на хосте, не в git.
- Прямой whois -h whois.tcinet.ru discozavr.ru с VDS: REGISTERED, DELEGATED, VERIFIED, created 2026-06-04T22:41:32Z, paid-till 2027, ns pinspb, registrar PIN-RU. (yandex.ru тоже ок).
- На VDS: whoisd (edge, pid ~261008) слушает 0.0.0.0:43 + 127:8043, /opt/whoisd/server.py (edge-вариант, 296 строк, is_useful, CACHE_TTL_OK/NEG, RU_UPSTREAM_* но не настроен — .ru идут через query_whois_local).
- Логи VDS whoisd (journalctl -u whoisd --since 2026-06-04): 22:31:55 q=discozavr.ru source=whois size=235 (no-entries от TCI), закешировано 24h. Позже 23:21 — свежий positive size=556.
- На прод-хосте (whois-watcher): whoisd (main/proxy, pid 938 → новые) слушает 127:43/8043, RU_UPSTREAM_HOST=<VDS-IP>, /opt/whoisd/server.py (длинный main-вариант). В 01:31:55 06-05: query=discozavr.ru source=whois_ru_upstream ok=1 bytes=235 → cache 24h. Позже served from cache.
- В кэше прод whoisd (скопирован /tmp): до сих пор "No entries" для pinbettng.ru, a.pinbetting.ru, xn--... (ok=1, source=whois_ru_upstream, ttl=86400, bytes~235). discozavr уже перезаписан positive.
- Корень: whois_valid (main) / is_useful (edge) — len>50 && !rate → useful/ok=true + TTL_OK=24h, даже если текст "No entries found for the selected source(s)".
- Аналогично на VDS: no-entries от TCI → useful + 24h на edge.
- Применены изменения (по аналогии с post-deploy hotfix'ами 0089/0090, только на хостах; в git whois-watcher — только отчёт):
  - Прод-хост /opt/whoisd/server.py: добавлен NO_DATA_RE (no entries / not found / free / available ...), в ru_upstream и whois-ветках: если negative text — ttl = RU_UPSTREAM_TTL_NEG / TTL_NEG (вместо OK), лог (neg).
  - VDS /opt/whoisd/server.py + /opt/whoisd-repo/server.py: добавлен NO_DATA_RE; is_useful теперь возвращает False для no-data текстов (negative идут в short CACHE_TTL_NEG путь, но raw "No entries" текст всё равно отдаётся whois/http-клиенту).
  - Systemd units: добавлены Environment=RU_UPSTREAM_TTL_NEG=3600 / CACHE_TTL_NEG=3600 (в [Service]); daemon-reload + restart whoisd на обоих.
- Верификация:
  - Прод whoisd: test-free домен (test-*-0093e.ru) → source=whois_ru_upstream ok=True ttl_remaining=3600 (short!), текст no-entries в data.
  - VDS whoisd: test-free → source=none ok=False (из-за is_useful), short internal ttl, текст no-entries в data.
  - discozavr сейчас positive на обоих (ttl 24h).
  - whoisd рестарты: active, свежий pid, /q/ отвечает.
- whois-watcher контейнеры не трогали (им не нужен ребилд — whoisd на хосте).
- Обновлено в ww.txt (кратко).

## Изменённые/новые файлы (только хосты + отчёт в git)

- /opt/whoisd/server.py (прод + VDS)
- /opt/whoisd-repo/server.py (VDS)
- /etc/systemd/system/whoisd.service (прод + VDS)
- docs/sessions/2026-06-07_task-0093-relay-stale-no-entries.md (новый)
- handoff/tasks/TASK-0093-relay-stale-no-entries.md (статус + session)
- handoff/INDEX.md (авто handoff.py)

## Коммиты

(после handoff.py done + push)

## Проверки

- Нет изменений в src/ (whois-watcher) → pytest/mypy/ruff/CI не применимы.
- Реальный whois + кэш: neg-ответы теперь ≤1ч (3600), позитивы 24ч. Лаг TCI (регистрация) не лечится здесь, но окно stale сокращено.
- 0092 (RDAP-verify в боте) + этот — в комбинации решают симптом "зарег. домен 2 суток «свободен»".

## Что осталось / следующий шаг

- Архитектор: `python3 scripts/handoff.py done TASK-0093`, обновить STATE.md (упомянуть 0093 как relay-side hardening + ссылка на whoisd-repo если вынесем), возможно завести таск на whoisd как отдельный проект (версионирование, тесты, деплой).
- Если TCI будет часто лагать на новых .ru — мониторить last_updated в ответах или добавить positive-only для .ru (state: REGISTERED) в парсер/who isd.
- whoisd на VDS/проде теперь с NO_DATA short-ttl; при следующем обновлении whoisd — перенести патч в whoisd-repo/scripts.

## Архитектурные решения / открытые вопросы

- whoisd (отдельный от whois-watcher) — кэширует "ответ реестра" (в т.ч. negative) с TTL по "useful vs error", а не по "registered vs free". Это ок для большинства, но для .ru new-reg (лаг TCI) + широкая детекция negative → 24h stale. 0093 сокращает TTL negative до 1ч.
- ok=true для "no entries" сохранён (чтобы бот-парсер и 0092 видели текст и могли отличать free от ошибки).
- VDS whoisd теперь шлёт no-entries как ok=false internal, но текст проходит — прокси (с патчем) приводит к ok=true + short ttl. UX для легит free .ru не сломан.

## Ссылки

- TASK-0091 (диагностика на проде)
- TASK-0092 (RDAP-verify + ADR 045)
- ADR 028 (whoisd / proxy)
- handoff/tasks/TASK-0093-relay-stale-no-entries.md
- /opt/whoisd/server.py (оба хоста) + юниты


## ОБНОВЛЕНИЕ (архитектор): патч перенесён в git whois-proxy

Хостовый патч whoisd версионирован: **nmetluk/whois-proxy** commit `2ae4442` (ADR 011) — `NO_DATA_RE` + `is_no_data()` + `NO_DATA_TTL=600` для ru_upstream/local whois веток; systemd-юниты обновлены. Хвост «whoisd вне git» закрыт: при следующем апдейте whoisd берётся из репо, патч не потеряется.
