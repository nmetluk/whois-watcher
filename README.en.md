# Whois Watcher

[![CI](https://github.com/nmetluk/whois-watcher/actions/workflows/ci.yml/badge.svg)](https://github.com/nmetluk/whois-watcher/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

[Русская версия →](README.md)

A free Telegram bot that watches your domains and sends reminders before
registration expires. It queries WHOIS at the registrar, compares with the
previous state, and notifies you when something changes or renewal is due.

## Features

- WHOIS lookup for any domain via RDAP, with WHOIS:43 fallback
- Track a portfolio of domains (up to 50,000 per user)
- Expiry reminders at 30 / 7 / 1 day — intervals are configurable
- Change notifications: registrar, nameservers, status flags
- Bulk import from TXT/CSV (`/download`) and CSV export (`/csv`)
- IDN support (`.рф`, `.中国`, etc.) — on input and in exports
- Bilingual UI (English / Russian), auto-detected from Telegram
- Per-user timezone, configurable reminder time of day
- Completely free, no ads, no tiers

## Quick start

### For users

Open [@whois_watcher_bot](https://t.me/whois_watcher_bot) in Telegram and
send `/start`. No sign-up, no payment, no personal data — just the domains
you want to watch.

### For developers

Requires: Python 3.11+, [uv](https://github.com/astral-sh/uv),
Docker with Compose.

```bash
git clone https://github.com/nmetluk/whois-watcher.git
cd whois-watcher

cp .env.example .env
# fill in BOT_TOKEN (from @BotFather), WEBHOOK_BASE_URL, WEBHOOK_SECRET

uv sync
docker compose up -d postgres redis
uv run alembic upgrade head

# run processes locally (for production, use `docker compose up -d`)
uv run python -m src.main           # bot (webhook server)
uv run python -m src.worker         # worker + scheduler
```

Full VPS deployment guide: [docs/deployment.md](docs/deployment.md).

## Bot commands

| Command | What it does |
|---------|--------------|
| `/start` | Welcome screen |
| `/whois <domain>` | Show WHOIS |
| `/add <domain>` | Start tracking |
| `/rmv <domain>` | Stop tracking |
| `/list` | List tracked domains with filters and pagination |
| `/csv` | Export everything to CSV |
| `/download` | Bulk import from TXT/CSV |
| `/notify <domain>` / `/unnotify <domain>` | Toggle notifications |
| `/settings` | Timezone, language, reminder days |
| `/stats` | Portfolio summary |
| `/check <domain>` | Force refresh (rate-limited) |
| `/help` | Help |
| `/delete_me` | Delete all my data |

Full UX spec: [docs/commands.md](docs/commands.md) (in Russian).

## Documentation

- [Architecture](docs/architecture.md) — three processes, shared cache, adaptive TTL
- [Commands](docs/commands.md) — UX specification
- [Deployment](docs/deployment.md) — step-by-step VPS guide
- [Decision log (ADR)](docs/decisions.md) — why each choice
- [Privacy policy](PRIVACY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Stack

- **Python 3.11+**, asyncio throughout
- **aiogram 3.x** via webhook (not long polling)
- **SQLAlchemy 2.0 async** + asyncpg, Alembic migrations
- **ARQ** — task queue on Redis
- **whoisit** for RDAP, native TCP client for WHOIS:43 with referral following
- **pydantic v2** + pydantic-settings
- **structlog** — JSON logs in production, ConsoleRenderer in dev
- **Sentry** SDK (optional) with secret filtering in `before_send`
- PostgreSQL 16, Redis 7, Docker Compose, Nginx + Let's Encrypt

## License

MIT. See [LICENSE](LICENSE).

## Contributing

Issues, pull requests, and discussions welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). If you find a security vulnerability,
please report it privately (contact in `CONTRIBUTING.md`) rather than
opening a public issue.
