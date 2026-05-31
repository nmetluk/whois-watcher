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
| v0.7.0 | RIR/ASN lookup integration (rir2localdb, ADR 031) | 2026-05-19 |
| v0.8.0 | DNS A/AAAA/NS monitoring (ADR 032) | 2026-05-22 |
| v0.8.1 | Wishlist ↔ tracking auto-promote (ADR 034) | 2026-05-28 |
| v0.9.0 | Поддомены / PSL / DNS-SSL у поддомена (ADR 035) | 2026-05-29 |
| v0.9.3 | Instance-тег в админ-алертах (ADR 019) | 2026-05-30 |
| v0.10.0 | Email intelligence: MX/SPF/DKIM/DMARC (ADR 036) | 2026-05-30 |
| v0.11.0 | Subdomain enumeration через crt.sh, on-demand (ADR 037) | 2026-05-30 |
| v0.11.1 | Wishlist — независимые списки (ADR 039) | 2026-05-30 |
| v0.12.0 | Periodic subdomain monitoring + алерты (ADR 038) | 2026-05-31 |

Patch-релизы (`.1`/`.2`) с фиксами — в CHANGELOG.md. Полный лог фич
каждого релиза — там же.

## Где мы сейчас

Дорожная карта **subdomain + domain-intelligence** (ADR 035–039) полностью
закрыта релизом **v0.12.0**. Работают пять осей наблюдения: WHOIS, SSL,
DNS (A/AAAA/NS) с ASN-фильтрацией, email-инфраструктура (MX/SPF/DKIM/DMARC)
и поддомены (enumeration + мониторинг новых/исчезнувших). Доска задач
(`handoff/INDEX.md`) пуста — это точка выбора следующего крупного этапа.

## v0.13 — Deep email + on-demand views (в работе, ADR 040)

Углубление почтового слоя и привязка deep-разбора/поддоменов к карточке `/whois`.

- [ ] Deep email-парсеры/коллекторы: SPF include-резолвинг (лимит 10 lookups),
  MTA-STS, TLS-RPT, DANE/TLSA, BIMI (TASK-0038)
- [ ] On-demand ARQ-задача `check_email_deep` + кэш `email_deep_cache` (TASK-0039)
- [ ] Инлайн **MX + краткий статус** SPF/DMARC в первом сообщении `/whois` +
  фикс «свежести» (плейсхолдер вместо пустоты) (TASK-0040)
- [ ] Кнопка «✉️ Глубокий e-mail» (on-demand, «⏳ ищу…») (TASK-0041)
- [ ] Кнопка «🛰 Поддомены» — переиспользует enumeration ADR 037 (TASK-0042)
- [ ] Аудит v0.13 (TASK-0043) → релиз v0.13.0 (TASK-0044)

## v1.0 — Public stable

Стабилизация публичного API и интерфейса для долговременной поддержки.
Перед стартом каждого пункта — отдельный ADR (design-first, как принято
в проекте), затем разбивка на исполнительские таски в `handoff/tasks/`.

- [ ] Веб-дашборд (read-only): список доменов, графики, фильтры
- [ ] Публичная HTTP API для интеграций (read-only)
- [ ] Командные / организационные аккаунты — общий портфель на группу
- [ ] Метрики Prometheus exporter и health-эндпойнты для k8s probes
- [ ] Парсер для большего числа ccTLD (.uk, .nl, .es, .br, .pl, .cz,
  .au, .ca, .jp) — фикстуры на основе реальных ответов

## Tech debt

Накопленные пометки «сделать лучше», без жёстких дат.

- [ ] **html.escape в остальных нотификациях.** В v0.12.0 (TASK-0037)
  экранирование добавлено только для subdomain-уведомлений. Та же
  defense-in-depth напрашивается в whois/ssl/dns/email change-нотификациях
  (значения интерполируются в `ParseMode.HTML`). Отдельным маленьким таском.
- [ ] **Миграция FSM с MemoryStorage на RedisStorage.** Все FSM-states
  (`AwaitingDomainArg`, `ListSearchStates`, `NotifyDaysStates`,
  `NotifySslDaysStates`, `NotifySubdomainIntervalStates`, `DownloadStates`,
  `SettingsStates`) хранятся в памяти процесса. State теряется при рестарте
  бота; реального time-based TTL нет, он эмулируется middleware
  `clear_state_on_command`. Переход на `RedisStorage(state_ttl=300)` даст
  устойчивость к рестартам и настоящий TTL. См. ADR 033 → Followup.
- [ ] DENIC: отдельный «expiry hidden by registry»-значок в `/list`
  и подсказка. Сейчас `.de` показывается как «нет данных», что
  вводит в заблуждение.
- [ ] Больше интеграционных тестов для ARQ-тасок (сейчас покрыты
  юнит-тестами с моками; нужны проходы через настоящие
  Postgres+Redis через `pytest-docker`).
- [ ] Бенчмарк `scheduler_tick` на 100K доменов — проверить, что
  выборка `next_check_at <= now()` остаётся быстрой (актуально и для
  нового `subdomain_scheduler_tick`).
- [ ] `MIGRATIONS.md` — гайд по созданию и проверке новых миграций.
- [ ] Документировать ADR 019 (дедупликация алертов): какие severity
  и частоту считаем нормальными — сейчас только в коде.

## Идеи на потом (не запланировано)

- Регистрация домена через бот (партнёрка с регистраторами)
- Поддержка whois-конкретного-регистратора с авторизацией (для
  частных TLD-зон, например `.cm` через NSI)
- Мониторинг репутации (RBL / SpamHaus)
- Алерты при появлении wishlist-домена в Certificate Transparency логах
  (early-signal, что домен начали использовать)
