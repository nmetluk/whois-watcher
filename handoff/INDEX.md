# INDEX — доска задач

> АВТО-генерируется `python scripts/handoff.py board`. Не править руками.

Всего задач: 37

| ID | Статус | Майлстоун | ADR | Область | Тема | Ветка |
|----|--------|-----------|-----|---------|------|-------|
| TASK-0036 | in_review | v0.12.0 | 038 | docs | Релиз v0.12.0 — мониторинг поддоменов (ADR 037+038) | task/0036-release-v0-12-0 |
| TASK-0001 | done | v0.8.1 | 034 | code | Багфикс wishlist ↔ tracked (авто-промоут) | task/0001-wishlist-tracked-fix |
| TASK-0002 | done | v0.9.0 | 035 | code | PSL — зависимость tldextract + src/utils/domains.py | task/0002-psl-utils-domains |
| TASK-0003 | done | v0.9.0 | 035 | code | Схема user_domains (registrable_domain, is_subdomain) + WHOIS-джойны | task/0003-subdomain-schema-whois-joins |
| TASK-0004 | done | v0.9.0 | 035 | code | Маршрутизация WHOIS на registrable-родителя (facade/scheduler) | task/0004-whois-parent-routing |
| TASK-0005 | done | v0.9.0 | 035 | code | UX поддоменов — /whois, /add, /list, локали | task/0005-subdomain-ux-locales |
| TASK-0006 | done | v0.9.0 | 035 | audit | Комплексный аудит v0.9.0 (поддомены/PSL) | — |
| TASK-0007 | done | v0.9.0 | — | audit | Аудит: v0.9.0 поддомены/PSL | — |
| TASK-0008 | done | v0.9.0 | 035 | code | Починить миграцию registrable_domain (не применяется на Postgres) | task/0008-fix-registrable-migration |
| TASK-0009 | done | v0.9.0 | 035 | infra | Smoke-test Alembic-миграций на эфемерном Postgres в CI | task/0009-migration-ci-smoke-test |
| TASK-0010 | done | v0.9.2 | 035 | code | Hardening tldextract — cache_dir, комментарий, no-network тест | task/0010-tldextract-hardening |
| TASK-0011 | done | v0.9.2 | 035 | docs | Доки — добавить tldextract/PSL в CLAUDE.md и architecture.md | task/0011-docs-tldextract-psl |
| TASK-0012 | done | v0.10.0 | 036 | docs | Дизайн ADR 036 — domain intelligence v0.10 (MX/SPF/DKIM/DMARC, subdomain enum) | — |
| TASK-0013 | done | v0.9.0 | — | code | Починить mypy type-narrowing в whois.py (красный CI с TASK-0005) | task/0013-mypy-narrowing-whois |
| TASK-0014 | done | v0.9.1 | — | docs | Релиз v0.9.1 — починенная миграция + CI/mypy фиксы | task/0014-release-v0-9-1 |
| TASK-0015 | done | v0.10.0 | 036 | code | Схема email_intel_cache + toggle'ы уведомлений (ADR 036) | task/0015-email-intel-schema |
| TASK-0016 | done | v0.10.0 | 036 | code | Сбор и парсеры MX/SPF/DKIM/DMARC + базовая диагностика (ADR 036) | task/0016-email-intel-parsers |
| TASK-0017 | done | v0.10.0 | 036 | code | ARQ-задачи и scheduler email-intel + уведомления (ADR 036) | task/0017-email-intel-tasks-scheduler |
| TASK-0018 | done | v0.10.0 | 036 | code | UX email-intel — блок в /whois, toggle'ы, локали (ADR 036) | task/0018-email-intel-ux-locales |
| TASK-0019 | done | v0.9.3 | 019 | code | Идентификатор инстанса (label + домен + IP) в каждом сообщении админ-канала | task/0019-admin-alert-instance-tag |
| TASK-0020 | done | v0.10.1 | — | code | Срочный фикс — кнопка «Мои домены» в /start не работает | task/0020-fix-start-my-domains-button |
| TASK-0021 | done | v0.11.0 | 037 | docs | Дизайн ADR 037 — subdomain enumeration через CT-логи (v0.11) | — |
| TASK-0022 | done | v0.11.0 | 037 | code | Схема subdomain_enum_cache + миграция (ADR 037) | task/0022-subdomain-enum-schema |
| TASK-0023 | done | v0.11.0 | 037 | code | crt.sh-клиент + парсер/нормализация + ARQ-задача (ADR 037) | task/0023-subdomain-enum-client |
| TASK-0024 | done | v0.11.0 | 037 | code | UX — команда /subdomains + opt-in отслеживание + локали (ADR 037) | task/0024-subdomain-enum-ux |
| TASK-0025 | done | v0.11.0 | 037 | code | Fast-follow по TASK-0023 — тесты scheduler, update_fail upsert, мелочи (ADR 037) | task/0025-subdomain-enum-followup |
| TASK-0026 | done | v0.12.0 | 038 | docs | Дизайн ADR 038 — мониторинг новых поддоменов + алерты (v0.12) | — |
| TASK-0027 | done | v0.12.0 | 038 | code | Схема — toggles track_subdomains/notify_subdomain_* + per-user интервал + миграция (ADR 038) | task/0027-subdomain-monitor-schema |
| TASK-0028 | done | v0.12.0 | 038 | code | Diff + scheduler мониторинга поддоменов + интеграция в check_subdomains (ADR 038) | task/0028-subdomain-monitor-diff-scheduler |
| TASK-0029 | done | v0.12.0 | 038 | code | Уведомления о новых/исчезнувших поддоменах + UX toggles/интервал + локали (ADR 038) | task/0029-subdomain-monitor-notify-ux |
| TASK-0030 | done | v0.12.0 | 038 | audit | Комплексный аудит v0.12 (мониторинг поддоменов, ADR 037+038) | — |
| TASK-0031 | done | v0.11.1 | 039 | code | Схема — отдельная таблица wishlist + миграция переноса (ADR 039) | — |
| TASK-0032 | done | v0.11.1 | 039 | code | Развязка wishlist↔tracking по коду + кнопка «убрать из wishlist» (ADR 039) | — |
| TASK-0033 | done | v0.12.0 | 038 | code | Реальные тесты fan-out notify_subdomain_changes (ADR 038) | task/0033-notify-subdomain-fanout-tests |
| TASK-0034 | done | v0.12.0 | 038 | code | Тесты success+diff→enqueue и baseline в check_subdomains (ADR 038) | task/0034-check-subdomains-success-enqueue-tests |
| TASK-0035 | done | v0.12.0 | 038 | code | Fan-out поддоменов — устранить N+1 и ordering-зависимый дедуп toggle'ов (ADR 038) | task/0035-subdomain-fanout-nplus1-toggle-dedup |
| TASK-0037 | done | v0.12.0 | 038 | code | Hardening поддоменов — html.escape в нотификациях + кап интервала FSM (ADR 038) | task/0037-subdomain-notify-hardening |
