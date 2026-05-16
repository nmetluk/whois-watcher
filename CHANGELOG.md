# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet — see [TODO.md](TODO.md) for the roadmap.

## [0.1.0] — 2026-05-16

First public release. MVP feature set, production-ready infrastructure.

### Added

- WHOIS lookup for any domain via RDAP, with WHOIS:43 fallback
- Domain tracking with adaptive re-check schedule (30 / 7 / 2 / 1 days
  to expiry → corresponding check interval)
- Shared WHOIS cache across all users (one record per domain)
- Expiry reminders at configurable days before expiration
- Change notifications for registrar, name servers, and EPP status flags
- `/csv` — export user portfolio as UTF-8 BOM CSV
- `/download` — bulk import from TXT/CSV with FSM-driven preview and
  rate-limiting (`MAX_DOWNLOADS_PER_DAY`, file size, per-user limit)
- `/whois`, `/add`, `/rmv`, `/list` (paginated + filters), `/check`,
  `/notify`, `/unnotify`, `/settings`, `/stats`, `/delete_me` commands
- Bilingual UI (Russian / English) with auto-detection from Telegram
- Per-user timezone and reminder time (`notify_at_hour`)
- IDN support (`.рф`, `.中国`, ...) via punycode normalization
- WHOIS parser support for `.com`, `.net`, `.org`, `.info`, `.io`,
  `.ru`, `.рф`, `.de`, `.it`, `.kz`, and many more
- WHOIS referral following for thin-WHOIS registries (Verisign etc.):
  second query to the registrar's WHOIS server for full data
- `WHOIS_SERVER_OVERRIDES` env: per-TLD WHOIS server override for hosts
  where default servers are unreachable (community mirrors for `.ru`)
- IANA discovery for unknown TLDs — parses both `refer:` and `whois:` keys
- Admin Telegram channel for system alerts (ADR 019) with Redis dedup;
  daily summary, cleanup cron jobs
- `/admin` command for operators (stats, manual alert)
- Sentry SDK integration with `before_send` filter that strips
  `*token*`/`*password*`/`*secret*`/auth headers and bulk WHOIS payloads
- structlog production logging: JSON renderer in `production`,
  ConsoleRenderer in `development`; `bind_log_context` for request/task
  scoped fields (`telegram_id`, `user_id`, `update_id`, `domain`)

### Infrastructure

- PostgreSQL 16 + Redis 7 + ARQ workers
- Three independent processes: bot (webhook), worker, scheduler
- Docker Compose deployment, Nginx + Let's Encrypt
- Webhook (not long polling), `X-Telegram-Bot-Api-Secret-Token` verified
- 328 tests passing; mypy strict; ruff and black clean
- GitHub Actions CI for lint + type-check + tests on every push and PR
