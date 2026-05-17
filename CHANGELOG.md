# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Per-domain notification toggle for owner (registrant) changes** —
  ``notify_registrant_change`` (раньше шёл через
  ``notify_registrar_change``-mapping, см. ADR 029).
- **Per-domain notification toggle for fetch problems** — ``notify_problem``.
- **Per-domain kill-switch** — ``is_muted`` boolean. Заменяет computed
  «все toggle'ы выключены»; при unmute индивидуальные настройки
  сохраняются.
- **Inline notification configurator UI** в карточке /whois: кнопка
  «⚙️ Уведомления» открывает интерактивный конфигуратор с toggle'ами
  всех 6 типов уведомлений, mute/unmute, и FSM-редактором списка дней
  предупреждения. Toggle перерисовывает клавиатуру через
  ``edit_message_reply_markup`` — без флуда в чат.

### Changed

- «Muted»-индикатор в /list теперь читает поле ``is_muted`` напрямую
  (раньше вычислялся как «все 4 toggle'а выключены»).
- Уведомления о смене владельца отделены от уведомлений о смене
  регистратора — пользователи, выключившие registrar_change, продолжат
  получать registrant-уведомления (default включён).
- ``expiry_scheduler`` SQL: добавлен фильтр ``ud.is_muted = false``.

### Database

- 3 новые колонки в ``user_domains``: ``is_muted`` (bool, default false),
  ``notify_registrant_change`` (bool, default true), ``notify_problem``
  (bool, default true). Миграция ``20260517_pernotif``, дефолты
  backwards-compat: поведение для существующих пользователей
  не меняется.

### Documentation

- Новый ADR 029 (per-domain notification settings — extended) +
  обновление CHANGELOG.

## [0.4.0] — 2026-05-17

### Changed

- WHOIS lookups now route through internal proxy gateway running on the
  host (`host.docker.internal:8043` from containers). The proxy handles
  RDAP, generic WHOIS, and RU-specific upstream via a dedicated RU-VDS.
  See [ADR 028](docs/decisions.md#028-whois-proxy-gateway-as-primary-lookup).
- 24-hour positive caching on proxy side reduces load on registries and
  improves response times.
- New `DataSource` literal values: `proxy_rdap`, `proxy_whois`,
  `proxy_whois_ru`, `proxy_none` — track which upstream the proxy used.

### Added

- `src/whois/proxy_client.py` — HTTP/JSON client for the proxy gateway
  (`lookup_via_proxy`, `proxy_healthcheck`, `ProxyUnreachable`).
- Proxy health monitoring: ARQ cron `proxy_health_check` runs every
  15 minutes, pings `/healthz`, sends critical alert to admin channel
  if the proxy is down.
- Source attribution in WHOIS data: `proxy_rdap`, `proxy_whois`,
  `proxy_whois_ru`, `proxy_none` to track upstream and cache status.
- Automatic fallback to direct RDAP/WHOIS:43 lookup when proxy is
  unreachable — bot remains functional during proxy downtime.
- Docker compose network configured to reach host-side proxy: pinned
  subnet `172.28.0.0/16`, explicit gateway in `extra_hosts`, and ufw
  allow rule (`ufw allow from 172.28.0.0/16 to any port 8043 proto tcp`)
  on the host. Docker's `host-gateway` magic doesn't work for
  user-defined compose networks — see ADR 028 for the trap.
- New [ADR 028](docs/decisions.md#028-whois-proxy-gateway-as-primary-lookup):
  WHOIS proxy gateway as primary lookup.

### Removed

- `WHOIS_SERVER_OVERRIDES` env variable and its validator (replaced by
  the proxy gateway).
- `server_overrides=` parameter of `whois_protocol.query_whois`.
- [ADR 023](docs/decisions.md#023-whois-server-overrides-per-tld-deprecated-in-v040)
  marked DEPRECATED (kept for historical reference).

### Fixed

- `.ru` / `.рф` / `.su` domains now consistently return full WHOIS data
  from non-RU IP addresses (previously blocked by TCI).

### Documentation

- Cross-referenced `scripts/deploy.sh` across README, ADR 027,
  CONTRIBUTING for long-term discoverability (back-dated to v0.3.x but
  landed after the v0.3.0 tag).

## [0.3.0] — 2026-05-17

### Added

- **Hidden `/version` command** with build info: short output for
  everyone (version + commit + build time), extended report for
  `ADMIN_USER_IDS` (uptime, Postgres/Redis health, storage counters,
  stack versions, GitHub commit link). Not registered in the BotFather
  menu and not mentioned in `/help`.
- **Search by substring in `/list`** via the new `🔍 Поиск` button and
  FSM input — supports both punycode and Unicode variants («пример»
  finds `xn--…`).
- **New `/list` filters:** `🚨 С проблемами` (critical EPP statuses —
  `clientHold`, `pendingDelete`, `serverHold`, `BLOCKED`, `failed`)
  and `💀 Истёкшие` (`expires_at < now()`).
- **Wishlist:** `/wishlist <domain>` or the inline button
  «🎯 Хочу когда освободится» in the `/whois` card. The bot re-checks
  wishlist domains every 24 hours and sends a one-shot notification
  when the domain becomes available, then auto-removes the
  subscription. Filter `🎯 Wishlist` in `/list` shows the active
  wishlist.
- **One-command deployment:** `scripts/deploy.sh` — clean working tree
  check → git pull → build info regen → docker build → alembic upgrade
  → recreate services → health verification.
- **`APP_VERSION` baked into build info** at deploy time: read from
  `pyproject.toml` via `tomllib` and written to `_build_info.py`
  alongside git metadata, so `/version` reports a real version in
  containers (where `importlib.metadata` returns `unknown` due to
  `uv sync --no-install-project`).

### Fixed

- **`/list` "CSV" button now exports the file directly** instead of
  responding with a hint to use the `/csv` command. Both entry points
  now share the same `send_user_csv_file` helper.
- **No bogus change notifications on first fetch after `/add`** —
  `compute_diff` was treating the NULL → real-value transition from
  the placeholder `whois_cache` row (inserted by `add_for_user` before
  `check_domain` ran) as a real change. Guard now also requires
  `old_data.is_registered=True`.
- **`/list` pagination no longer resets the active filter** when
  paging prev/next — state is persisted in Redis `list_state:{user_id}`
  (TTL 30 min) along with the search query.

### Database

- `user_domains.is_wishlist BOOLEAN NOT NULL DEFAULT false` (migration
  `20260517_wishlist`). Existing rows are unaffected.
- New `notification_type='wishlist_available'` value used in
  `sent_notifications` for audit logging.

## [0.2.0] — 2026-05-17

### Added — Enhanced WHOIS display (Stage 8)

- **Owner section in `/whois` card** — extracts `registrant`, `admin`,
  `tech`, `abuse`, `billing` contacts from both RDAP (entities + vCard +
  RFC 9537 `redacted[]`) and textual WHOIS (thick gTLD, TCINET `.ru`,
  NIC.it dotted keys, AFNIC, DENIC). Shows owner organization with
  country, or honest "hidden (private individual)" / "hidden (privacy
  protected)" labels when registry redacts data.
- **Localized status names** — raw EPP codes (`clientTransferProhibited`,
  `pendingDelete`) are translated to human-readable text with severity
  highlighting (critical → warning → info → normal). Unknown codes fall
  back to a humanized form (`clientHold` → "Client hold"). Trivial
  `ok`/`active` are hidden when other statuses are present.
- **Registrant change notifications** — new `notify` types: `registrant`
  (organization changed), `registrant_privacy_revealed` (was hidden,
  now public), `registrant_privacy_hidden` (was public, now hidden).
  Email/phone changes are intentionally ignored to avoid notification
  noise. Subscribed via the existing `notify_registrar_change` flag —
  no new per-domain switch.
- **Human-readable "full WHOIS" file** — the "Full response" button now
  returns a `.txt` with a structured header (domain / timeline /
  registrar / contacts / status / nameservers / DNSSEC) **plus** the
  raw source data: pretty-printed JSON for RDAP, original text for
  WHOIS:43. Replaces the previous Python `repr(dict)` for RDAP domains.

### Changed

- `WhoisData` gains `contacts: list[WhoisContact]` and `registrant` /
  `admin` / `tech` convenience properties.
- `whois_cache` schema adds denormalized `registrant_*` columns and a
  JSONB `contacts_data` column (migration `20260516_registrant`,
  additive; existing rows fill on next scheduled check).
- Sentry `before_send` masks `registrant*`, `admin_email`, `admin_phone`,
  `tech_email`, `tech_phone`, `contacts_data` keys — public WHOIS data
  shouldn't sit in error trackers.

### Migration notes

- `alembic upgrade head` adds nullable columns. Existing cached domains
  show no Owner section until the next plan-driven `check_domain` run
  fills the new fields. To force-refresh a specific domain, press the
  "🔄 Обновить" button in its `/whois` card.

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
