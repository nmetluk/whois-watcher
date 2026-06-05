# 2026-06-07 — TASK-0091: Прод-диагностика — зарегистрированный домен 2 суток показывается «свободен» (discozavr.ru)

**Дата:** 2026-06-07 · **Таск:** TASK-0091 · **Ветка:** task/0091-prod-diagnose-stale-free
· **Исполнитель:** grok (executor)

## Задача

Прод-диагностика симптома: discozavr.ru (зарегистрирован ~2 суток назад) показывается ботом как «свободен» в /whois и карточках, хотя внешние whois/реестр видят регистрацию. Кэши (бот 6ч, proxy 24ч) к моменту жалобы уже истекли, live-запрос шёл. Гипотеза: парсер в src/whois/parser.py:_looks_like_not_found (substring match по NOT_FOUND_PATTERNS) трактует текст ошибки/«no entries» от RU-relay как «free».

Никаких правок кода — только сбор улик + вывод.

## Выполнено (шаги по тасу)

### 1. Что в whois_cache бота (psql)

Домен **отсутствует** в whois_cache (0 rows):

```sql
SELECT domain, fetched_at, next_check_at, fail_count, last_error, registrar, status, expires_at
FROM whois_cache
WHERE domain='discozavr.ru';
-- 0 rows
```

Причина: whois_cache ведётся только для доменов, на которые есть подписка в user_domains (см. delete_orphans в репозитории). on-demand /whois и /check не обязательно оставляют след в persistent кэше (или запись была удалена как orphan). «raw_data кэша», упомянутая в тикете — это, скорее всего, данные из ответа прокси (или логи).

### 2. Что отвечает proxy прямо сейчас (live + cached)

```bash
curl -s "http://127.0.0.1:8043/q/discozavr.ru"   # (актуальный эндпоинт; в тасу был /whois?... — устарел)
```

Полный ответ (мета + data):

```json
{
  "query": "discozavr.ru",
  "source": "whois_ru_upstream",
  "cached": true,
  "fetched_at": 1780612315,
  "ttl_remaining": 9070,
  "ok": true,
  "data": "% TCI Whois Service. Terms of use:\n% https://tcinet.ru/documents/whois_ru_rf.pdf (in Russian)\n% https://tcinet.ru/documents/whois_su.pdf (in Russian)\n\nNo entries found for the selected source(s).\n\nLast updated on 2026-06-04T22:28:01Z\n\n",
  "error": null
}
```

**Ключевой текст, который ушёл в парсер:** `No entries found for the selected source(s).`

(Это cached-ответ proxy, возраст ~1 день на момент снятия; ttl_remaining ~2.5ч.)

### 3. Что отвечает TCI напрямую (whois -h whois.tcinet.ru)

С хоста (порт 43):

```
whois -h whois.tcinet.ru discozavr.ru
connect: Network is unreachable
```

(Прямой egress на 43/tcp ограничен в этом окружении; прокси имеет доступ через свой RU-relay на отдельном VDS. Это соответствует архитектуре ADR 028.)

Для сравнения — известный зарегистрированный:

```
whois -h whois.tcinet.ru yandex.ru  (через proxy даёт state: REGISTERED, DELEGATED, VERIFIED)
```

### 4. Реакция парсера / бота (симуляция live-запроса)

Запущено внутри ww-worker (точно тот же код, что в прод):

```python
text = """% TCI Whois Service. ...
No entries found for the selected source(s).
Last updated on 2026-06-04T22:28:01Z
"""
print(_looks_like_not_found(text))  # → True
d = parse_whois_text(text, "discozavr.ru")
print(d.is_registered)  # → False
```

**Вывод:** live-запрос (через proxy → whois_ru_upstream) → текст с "No entries found" → _looks_like_not_found (any(pattern in lower for pattern in NOT_FOUND_PATTERNS)) → WhoisData(is_registered=False).

Паттерны включают "no entries found", "not found", "no information available", "status: free" и т.д. — substring по всему телу ответа.

### Дополнительные улики

- Dig NS/A для discozavr.ru → пусто (в отличие от yandex.ru).
- docker compose logs ... | grep -i discozavr → ничего за последние часы/дни (домен не в tracked, on-demand не всегда логирует raw на info-уровне).
- Proxy healthz: ok.
- Для yandex.ru тот же путь даёт корректный REGISTERED + ns + created.

## Вывод (где родился «свободен»)

**relay (TCI / whois_ru_upstream) + parser.**

- RU-relay (через proxy) вернул «No entries found for the selected source(s).» (live на момент запроса после истечения кэша proxy).
- Парсер (parse_whois_text → _looks_like_not_found) по текущему дизайну (широкий NOT_FOUND_PATTERNS, поиск подстроки по всему тексту) интерпретировал это как is_registered=False.
- Это точно соответствует главной гипотезе таска: «Если RU-relay/proxy на сбое отдаёт текст ошибки/HTML/рейтлимит TCI — это трактуется как „домен свободен“ (класс „сбой ≠ свободен“)».

Бот-кэш (whois_cache) здесь ни при чём — домен не tracked (0 rows), on-demand пути ( /whois, /check, webapp) используют тот же proxy+parser pipeline.

Возможные первопричины на стороне relay (не в этом репо):
- Лаг появления новой регистрации в TCI whois (новые домены .ru иногда не сразу видны в whois после оплаты/регистрации у партнёра).
- Transient "no entries" от relay при перегрузке / специфическом upstream.
- Proxy выбрал whois_ru_upstream и закешировал negative-like ответ на 24ч (хотя ok:true).

Прямого бага в коде бота (кроме известной широкости free-детекции) не найдено.

## Что не делалось (по правилам таска)

- Никаких код-фиксов, миграций, правок парсера.
- БД только SELECT (никаких upsert/delete).
- Прод не рестартовался, контейнеры не пересобирались.
- Не трогали .env, IP, реальные tracked-домены пользователей.

## Кандидат в следующий таск (для архитектора)

**TASK-0092:** Ужесточить free-детекцию «сбой/нет-данных ≠ свободен».
- Разделить «точно свободен» (статус free/available от реестра, конкретные фразы) и «нет данных / ошибка upstream».
- Для .ru/.рф/.su — доверять только наличию `state: REGISTERED` или эквивалента, а не отсутствию записей.
- При "no entries" от whois_ru_upstream — возвращать WhoisError(dns_unreachable / upstream_unavailable) или is_registered=None с last_error, а не is_registered=False.
- Добавить тесты на синтетические "No entries found..." + реальные ответы TCI.
- Обновить NOT_FOUND_PATTERNS → более точные per-TLD паттерны (или positive "state: REGISTERED").
- Обновить форматтеры карточек / UX (показывать «не удалось проверить» вместо «свободен»).

После подтверждения гипотезы этим таском — заводить 0092.

## Файлы (только отчёт)

- `docs/sessions/2026-06-07_task-0091-prod-diagnose-stale-free.md` (новый)

## Проверки

- handoff.py validate (будет после done)
- Нет изменений в src/ → pytest/mypy/ruff не нужны.
- Real-world: curl proxy + parse внутри контейнера воспроизвели симптом 1:1.

## Следующий шаг

Архитектор: если вывод принят — `handoff.py done TASK-0091`, завести TASK-0092 (парсер/диагностика free), обновить STATE.md. При необходимости — редеплой не требуется (только отчёт).

## Ссылки

- TASK-0091 (этот)
- ADR 028 (proxy gateway)
- TASK-0079 (похожий класс: DNS failure vs "no records" в email-слое)
