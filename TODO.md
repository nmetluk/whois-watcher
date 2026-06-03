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

## v0.14 — Стабилизация / тех-долг (в работе, ADR 041)

Релиз без новых пользовательских фич — погашение накопленного долга.

- [ ] html.escape во всех change-нотификациях (TASK-0049)
- [ ] FSM `MemoryStorage`→`RedisStorage` + TTL (ADR 041, TASK-0050)
- [ ] DENIC «expiry скрыт реестром» — значок в `/list` (TASK-0051)
- [ ] Интеграционные тесты ARQ на pytest-docker + бенчмарк scheduler (TASK-0052)
- [x] Доки: MIGRATIONS.md + нормы дедупликации алертов (TASK-0053)
- [ ] Аудит v0.14 (TASK-0054) → релиз v0.14.0 (TASK-0055)

## v0.15 — Админ/ops-слой (в работе, ADR 042)

Операционный слой для эксплуатации прода (изменение плана 2026-06-08).

- [ ] Аудит-лог `audit_log` + helper `audit()` (retention 90д) (TASK-0057)
- [ ] Ежечасный бекап Postgres (pg_dump, ротация 36, verify) (TASK-0058)
- [ ] Ежечасный ops-отчёт в админ-канал + статус бекапа (TASK-0059)
- [ ] Дневной графический отчёт 21:00 МСК (matplotlib); 06:00-текст остаётся (TASK-0060)
- [ ] Вписать `audit()` в инцидент-точки + retention-cron (TASK-0061)
- [ ] Аудит v0.15 (TASK-0062) → релиз v0.15.0 (TASK-0063)

## v0.16 — WebApp-слой (ADR 043)

Telegram WebApp / mini-app. Дизайн в репо: `design/webapp/v1/` (PIN Voice, 6 экранов, RU).

- [x] ADR 043 + импорт дизайна в `design/webapp/v1/` (TASK-0064)
- [ ] Backend: initData auth + read API `/api/webapp` (TASK-0066)
- [ ] Frontend foundation: Vite+React, токены PIN Voice, Telegram SDK, nginx (TASK-0067)
- [ ] Экраны: список доменов + карточка домена (TASK-0068)
- [ ] Экраны: дашборд + календарь + алерты + «Ещё» (TASK-0069)
- [ ] Write-действия (тогглы/add/remove/массовые/настройки/импорт) (TASK-0070)
- [ ] Аудит v0.16 (TASK-0071) → релиз v0.16.0 (TASK-0072)

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
- [x] `MIGRATIONS.md` — гайд по созданию и проверке новых миграций.
- [x] Документировать ADR 019 (дедупликация алертов): какие severity
  и частоту считаем нормальными — сейчас только в коде.

## Идеи на потом (не запланировано)

- Регистрация домена через бот (партнёрка с регистраторами)
- Поддержка whois-конкретного-регистратора с авторизацией (для
  частных TLD-зон, например `.cm` через NSI)
- Мониторинг репутации (RBL / SpamHaus)
- Алерты при появлении wishlist-домена в Certificate Transparency логах
  (early-signal, что домен начали использовать)
