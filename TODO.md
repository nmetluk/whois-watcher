# Roadmap

История релизов — в [CHANGELOG.md](CHANGELOG.md). Этот файл описывает
план следующих версий.

## Released

| Версия | Тема | Дата |
|--------|------|------|
| v0.1.0 | MVP | 2026-05-16 |
| v0.2.0 | Enhanced WHOIS display | 2026-05-17 |
| v0.3.0 | Diagnostics, search, wishlist | 2026-05-17 |
| v0.4.0 | Own WHOIS proxy gateway | 2026-05-17 |
| v0.5.0 | Per-domain notification settings | 2026-05-17 |
| v0.6.0 | SSL Certificate Monitoring | 2026-05-17 |
| v0.6.1 | SSL patches (bootstrap + no_https classification) | 2026-05-17 |

Полный лог фич каждого релиза — в CHANGELOG.md.

## v0.7 — RIR/ASN lookup integration (planned)

Универсальный HTTP-клиент к сервису `rir2localdb`
(https://github.com/nmetluk/rir2localdb), который зеркалит данные
пяти RIR (AFRINIC, APNIC, ARIN, LACNIC, RIPE NCC) и отдаёт
whois-подобную информацию по IP и ASN через REST API.

Это **инфраструктурный** этап — закладывает фундамент для ASN-aware
фич в v0.8. Сам по себе нигде в UI/мониторинге пока не используется.

- [ ] Новый модуль `src/rir_client/` — HTTP/JSON клиент
  - `lookup_ip(addr)` → IPAllocation | IPError
  - `lookup_asn(num)` → ASNAllocation | ASNError
  - `healthcheck()` → bool
- [ ] Настройки: `RIR2LOCALDB_URL`, `RIR2LOCALDB_TIMEOUT`,
  `RIR2LOCALDB_ENABLED`
- [ ] Docker network `extra_hosts` для подключения к host-side
  `rir2localdb` (по аналогии с whois proxy в ADR 028)
- [ ] ARQ cron `rir_health_check` — алерты в admin-канал при падении
- [ ] ADR 031 — universal RIR client design
- [ ] Тесты (unit + smoke против реального сервиса на хосте)

**Out of scope для v0.7:** использование RIR-данных где-либо в UI
или change-уведомлениях. Применение в v0.8.

## v0.8 — DNS A/AAAA monitoring (planned)

Опирается на RIR client из v0.7 — DNS-мониторинг с ASN-фильтрацией
для устранения шума от CDN round-robin.

- [ ] Новая таблица `dns_cache` (A/AAAA/NS, ASN per IP, TTL, adaptive
  scheduling)
- [ ] 5 новых полей на `user_domains`: `track_dns`,
  `notify_dns_a_change`, `notify_dns_aaaa_change`,
  `notify_dns_ns_change`, `notify_dns_unreachable`
- [ ] Модуль `src/dns_monitor/` — async DNS resolver + ASN enrichment
  через rir_client
- [ ] Cron `dns_scheduler_tick`, `dns_reminders_scheduler`
- [ ] Уведомления: смена ASN A/AAAA (фильтр от CDN-шума), смена NS,
  became unresolvable, расхождение DNS-NS vs WHOIS-NS
- [ ] `/whois` карточка — DNS-блок с подсветкой DNS-NS vs WHOIS-NS
  расхождения (critical security signal)
- [ ] ADR 032 — DNS monitoring rationale

## v1.0 — Public stable

Стабилизация публичного API и интерфейса для долговременной поддержки.

- [ ] Веб-дашборд (read-only): список доменов, графики, фильтры
- [ ] Публичная HTTP API для интеграций (read-only)
- [ ] Командные / организационные аккаунты — общий портфель на группу
- [ ] Метрики Prometheus exporter и health-эндпойнты для k8s probes
- [ ] Парсер для большего числа ccTLD (.uk, .nl, .es, .br, .pl, .cz,
  .au, .ca, .jp) — фикстуры на основе реальных ответов

## Tech debt

Накопленные пометки «сделать лучше», без жёстких дат.

- [ ] DENIC: отдельный «expiry hidden by registry»-значок в `/list`
  и подсказка. Сейчас `.de` показывается как «нет данных», что
  вводит в заблуждение
- [ ] Больше интеграционных тестов для ARQ-тасок (сейчас покрыты
  юнит-тестами с моками; нужны проходы через настоящие
  Postgres+Redis через `pytest-docker`)
- [ ] Бенчмарк `scheduler_tick` на 100K доменов — проверить, что
  выборка `next_check_at <= now()` остаётся быстрой
- [ ] `MIGRATIONS.md` — гайд по созданию и проверке новых миграций
- [ ] Документировать ADR 019 (дедупликация алертов): какие severity
  и частоту считаем нормальными — сейчас только в коде
- [ ] Release page для v0.6.1 на GitHub UI (сейчас только tag, без
  оформления). Не критично — для patch-релиза tag достаточно
- [ ] **v0.8.x: миграция FSM с MemoryStorage на RedisStorage**. Сейчас
      все FSM-states (`AwaitingDomainArg`, `ListSearchStates`,
      `NotifyDaysStates`, `NotifySslDaysStates`, `DownloadStates`,
      `SettingsStates`) хранятся в памяти процесса. State теряется при
      рестарте бота; реального time-based TTL нет, он эмулируется
      middleware `clear_state_on_command`. Переход на
      `RedisStorage(state_ttl=300)` даст устойчивость к рестартам и
      настоящий TTL. См. ADR 033 → Followup.

## Идеи на потом (не запланировано)

- Регистрация домена через бот (партнёрка с регистраторами)
- Поддержка whois-конкретного-регистратора с авторизацией (для
  частных TLD-зон, например `.cm` через NSI)
- Мониторинг репутации (RBL / SpamHaus)
- Алерты при появлении домена в Certificate Transparency логах
  (для wishlist)
