# INDEX — доска задач

> АВТО-генерируется `python scripts/handoff.py board`. Не править руками.

Всего задач: 13

| ID | Статус | Майлстоун | ADR | Область | Тема | Ветка |
|----|--------|-----------|-----|---------|------|-------|
| TASK-0010 | open | v0.9.0 | 035 | code | Hardening tldextract — cache_dir, комментарий, no-network тест | — |
| TASK-0011 | open | v0.9.0 | 035 | docs | Доки — добавить tldextract/PSL в CLAUDE.md и architecture.md | — |
| TASK-0012 | open | v0.10.0 | 036 | docs | Дизайн ADR 036 — domain intelligence v0.10 (MX/SPF/DKIM/DMARC, subdomain enum) | — |
| TASK-0009 | claimed | v0.9.0 | 035 | infra | Smoke-test Alembic-миграций на эфемерном Postgres в CI | task/0009-migration-ci-smoke-test |
| TASK-0001 | done | v0.8.1 | 034 | code | Багфикс wishlist ↔ tracked (авто-промоут) | task/0001-wishlist-tracked-fix |
| TASK-0002 | done | v0.9.0 | 035 | code | PSL — зависимость tldextract + src/utils/domains.py | task/0002-psl-utils-domains |
| TASK-0003 | done | v0.9.0 | 035 | code | Схема user_domains (registrable_domain, is_subdomain) + WHOIS-джойны | task/0003-subdomain-schema-whois-joins |
| TASK-0004 | done | v0.9.0 | 035 | code | Маршрутизация WHOIS на registrable-родителя (facade/scheduler) | task/0004-whois-parent-routing |
| TASK-0005 | done | v0.9.0 | 035 | code | UX поддоменов — /whois, /add, /list, локали | task/0005-subdomain-ux-locales |
| TASK-0006 | done | v0.9.0 | 035 | audit | Комплексный аудит v0.9.0 (поддомены/PSL) | — |
| TASK-0007 | done | v0.9.0 | — | audit | Аудит: v0.9.0 поддомены/PSL | — |
| TASK-0008 | done | v0.9.0 | 035 | code | Починить миграцию registrable_domain (не применяется на Postgres) | task/0008-fix-registrable-migration |
| TASK-0013 | done | v0.9.0 | — | code | Починить mypy type-narrowing в whois.py (красный CI с TASK-0005) | task/0013-mypy-narrowing-whois |
