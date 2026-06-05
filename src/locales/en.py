"""English locale. Mirrors the keys in ``ru.py``.

If a key is missing here, the locale resolver falls back to ``ru``.
"""

from __future__ import annotations

from src.locales.ru import StatusSeverity

# WHOIS status code → (severity, English text, emoji_override). See ru.py for
# the schema; this table mirrors the keys but with English translations.
WHOIS_STATUSES: dict[str, tuple[StatusSeverity, str, str | None]] = {
    "ok": ("normal", "Active", "🟢"),
    "active": ("normal", "Active", "🟢"),
    "inactive": ("warning", "Not active", "🟡"),
    "clientTransferProhibited": ("info", "Transfer locked (registrar)", "🔒"),
    "clientUpdateProhibited": ("info", "Updates locked (registrar)", "🔒"),
    "clientDeleteProhibited": ("info", "Delete locked (registrar)", "🔒"),
    "clientHold": ("critical", "On hold by registrar", "🚨"),
    "clientRenewProhibited": ("info", "Auto-renew disabled by registrar", "🔒"),
    "serverTransferProhibited": ("info", "Transfer locked (registry)", "🔒"),
    "serverUpdateProhibited": ("info", "Updates locked (registry)", "🔒"),
    "serverDeleteProhibited": ("info", "Delete locked (registry)", "🔒"),
    "serverRenewProhibited": ("info", "Renew locked (registry)", "🔒"),
    "serverHold": ("critical", "On hold by registry", "🚨"),
    "pendingCreate": ("info", "Registration pending", "🕘"),
    "pendingDelete": ("critical", "Pending delete — will be removed soon", "⏳"),
    "pendingTransfer": ("warning", "Transfer pending", "🔄"),
    "pendingUpdate": ("info", "Update pending", "🕘"),
    "pendingRenew": ("info", "Renewal pending", "🕘"),
    "pendingRestore": ("warning", "Restore pending", "🔄"),
    "redemptionPeriod": ("warning", "Redemption period", "⚠️"),
    "addPeriod": ("info", "Add grace period", "📅"),
    "autoRenewPeriod": ("info", "Auto-renew grace period", "📅"),
    "renewPeriod": ("info", "Renew grace period", "📅"),
    "transferPeriod": ("info", "Transfer grace period", "📅"),
    "REGISTERED": ("normal", "Registered", None),
    "DELEGATED": ("normal", "Delegated", None),
    "VERIFIED": ("normal", "Verified", None),
    "NOT DELEGATED": ("warning", "Not delegated", "⚠️"),
    "BLOCKED": ("critical", "Blocked", "🚨"),
    "connect": ("normal", "Connected", "🟢"),
    "failed": ("critical", "Delegation failed", "🚨"),
    "free": ("info", "Free", None),
    "ACTIVE": ("normal", "Active", "🟢"),
    "REDEMPTION": ("warning", "Redemption period", "⚠️"),
    "FROZEN": ("warning", "Frozen", "⚠️"),
}


LOCALE: dict[str, str] = {
    # ------------------------------------------------------------------
    # /start, /help, /cancel
    # ------------------------------------------------------------------
    "start.greeting": (
        "👋 Hi! I track your domains and remind you about registration expiry.\n"
        "\n"
        "🔧 What I can do:\n"
        "/whois &lt;domain&gt; — check WHOIS\n"
        "/add &lt;domain&gt; — add to tracking\n"
        "/list — your domains\n"
        "/csv — export to CSV\n"
        "/download — bulk import\n"
        "/webapp — portfolio dashboard (WebApp)\n"
        "/settings — settings\n"
        "/help — full help\n"
        "\n"
        "💡 You can just send me a domain — I'll show its WHOIS.\n"
        "\n"
        "🆓 The service is completely free."
    ),
    "help.body": (
        "📖 <b>Help</b>\n"
        "\n"
        "<b>Domain lookup</b>\n"
        "/whois &lt;domain&gt; — show WHOIS\n"
        "/check &lt;domain&gt; — force refresh (once per day)\n"
        "/subdomains &lt;domain&gt; — find subdomains (via crt.sh)\n"
        "\n"
        "<b>Tracking</b>\n"
        "/add &lt;domain&gt; — add a domain\n"
        "/rmv &lt;domain&gt; — remove a domain\n"
        "/list — your list with pagination and filters\n"
        "/notify &lt;domain&gt; — enable notifications\n"
        "/unnotify &lt;domain&gt; — disable notifications\n"
        "\n"
        "<b>Import / export</b>\n"
        "/csv — export your list as CSV\n"
        "/download — bulk import from TXT/CSV\n"
        "\n"
        "<b>Other</b>\n"
        "/webapp — portfolio dashboard (WebApp inside Telegram)\n"
        "/settings — timezone, reminder time, language\n"
        "/stats — portfolio statistics\n"
        "/cancel — cancel current action\n"
        "/delete_me — delete all data\n"
        "\n"
        "💡 Just send a domain — I'll show WHOIS without a command."
    ),
    "cancel.done": "Cancelled.",
    "cancel.nothing": "Nothing to cancel.",
    # ------------------------------------------------------------------
    # FSM-flow for missing-argument commands (ADR 033)
    # ------------------------------------------------------------------
    "commands.cmd_arg.prompt": "Send a domain for /{cmd}. /cancel to abort.",
    "commands.cmd_arg.confirm": "Run <b>/{cmd} {domain}</b>?",
    "commands.cmd_arg.yes": "✅ Yes",
    "commands.cmd_arg.no": "❌ No",
    "commands.cmd_arg.invalid": (
        "<code>{input}</code> doesn't look like a domain. Try again or /cancel."
    ),
    "commands.cmd_arg.too_many": (
        "Found multiple domains, I'll take the first: <code>{domain}</code>. "
        "For bulk import use /download."
    ),
    "commands.cmd_arg.cancelled": "Cancelled.",
    "commands.cmd_arg.executing": "Running /{cmd} {domain}…",
    "commands.cmd_arg.stale": "No longer relevant.",
    # ------------------------------------------------------------------
    # Inline buttons
    # ------------------------------------------------------------------
    "button.check_domain": "🌐 Check domain",
    "button.my_domains": "📋 My domains",
    "button.settings": "⚙️ Settings",
    "button.webapp": "📱 Dashboard (WebApp)",
    "button.follow": "👁 Track",
    "button.unfollow": "🗑 Stop tracking",
    "button.refresh": "🔄 Refresh",
    "button.raw": "📄 Raw response",
    "button.subdomains": "🛰 Subdomains",
    "button.deep_email": "✉️ Deep email",
    "deep_email.searching": "⏳ Searching deep email for {domain}…",
    "button.dns_report": "🧾 DNS report",
    "dns_report.searching": "⏳ Building full DNS report for {domain} — sending as a file…",
    "deep_email.header": "Deep email for {domain}",
    "deep_email.no_data": "No deep email data.",
    "deep_email.section_spf": "SPF (recursive)",
    "deep_email.spf_none": "no records",
    "deep_email.spf_stats": "lookups: {count}",
    "deep_email.exceeds_limit": "limit exceeded",
    "deep_email.section_mta_sts": "MTA-STS",
    "deep_email.mta_mode": "mode: {mode}",
    "deep_email.mta_max_age": "max-age: {seconds}s",
    "deep_email.mta_reachable": "policy reachable",
    "deep_email.section_tls_rpt": "TLS-RPT",
    "deep_email.tls_rpt_present": "record present",
    "deep_email.tls_rpt_rua": "rua: {rua}",
    "deep_email.tls_rpt_none": "no record",
    "deep_email.section_dane": "DANE / TLSA (per MX)",
    "deep_email.dane_none": "no data",
    "deep_email.section_bimi": "BIMI",
    "deep_email.bimi_present": "present",
    "deep_email.bimi_none": "no record",
    "deep_email.fetched_at": "collected: {date}",
    "button.notify_on": "🔔 Turn back on",
    "button.cancel": "❌ Cancel",
    "button.back": "◀️ Back",
    # Stage 11 — notification configurator
    "notify_config.button": "⚙️ Notifications",
    "notify_config.title": "⚙️ <b>Notification settings</b> for {domain}",
    "notify_config.days_label_default": (
        "🔔 <b>Warning days:</b> {days}\n" "   <i>(using global settings)</i>"
    ),
    "notify_config.days_label_custom": (
        "🔔 <b>Warning days:</b> {days}\n" "   <i>(per-domain override)</i>"
    ),
    "notify_config.types_label": "<b>Notification types:</b>",
    "notify_config.muted_yes": "🔇 <b>Fully muted:</b> on",
    "notify_config.muted_no": "🔇 <b>Fully muted:</b> off",
    "notify_config.edit_days": "📅 Change warning days",
    "notify_config.mute_all": "🔇 Mute all",
    "notify_config.unmute_all": "🔔 Unmute",
    "notify_config.toggle.on": "✅",
    "notify_config.toggle.off": "❌",
    "notify_config.type.expiry": "Expiry warnings",
    "notify_config.type.registrar_change": "Registrar change",
    "notify_config.type.ns_change": "NS change",
    "notify_config.type.status_change": "Status change",
    "notify_config.type.registrant_change": "Owner change",
    "notify_config.type.problem": "Check problems",
    "notify_config.feedback_on": "✅ Enabled: {type}",
    "notify_config.feedback_off": "❌ Disabled: {type}",
    "notify_config.feedback_muted": "🔇 All notifications muted",
    "notify_config.feedback_unmuted": "🔔 Unmuted",
    "notify_config.not_tracked": (
        "❌ This domain is not tracked. Add it via /add or the «👁 Track» button."
    ),
    "notify_config.days_prompt": (
        "Type days separated by commas (e.g. <code>60,30,14,7,3,1</code>).\n\n"
        "/default — use global settings\n"
        "/cancel — keep current"
    ),
    "notify_config.days_invalid": (
        "❌ Invalid format. Use numbers separated by commas (1–365, "
        "no more than 10 values). Example: <code>30,7,1</code>"
    ),
    "notify_config.days_saved_override": "✅ Saved: warn at {days}",
    "notify_config.days_saved_default": "✅ Reverted to global settings",
    "notify_config.days_unchanged": "Warning days left unchanged.",
    # SSL (Stage 12, ADR 030)
    "notify_config.ssl_days_label_default": (
        "🔒 <b>SSL warning days</b> (global): warn {days} day(s) before expiry"
    ),
    "notify_config.ssl_days_label_custom": (
        "🔒 <b>SSL warning days</b> (for this domain): warn at {days} day(s)"
    ),
    "notify_config.edit_ssl_days": "🔒 Change SSL warning days",
    "notify_config.ssl_days_prompt": (
        "Type days separated by commas for SSL certificate (e.g. "
        "<code>14,7,3,1</code>).\n\n"
        "/default — use global settings\n"
        "/cancel — keep current"
    ),
    "notify_config.ssl_days_saved_override": "✅ SSL days saved: warn at {days}",
    "notify_config.ssl_days_saved_default": "✅ SSL: reverted to global settings",
    "notify_config.type.track_ssl": "SSL monitoring",
    "notify_config.type.ssl_expiry": "SSL expiry",
    "notify_config.type.ssl_change_issuer": "SSL certificate change",
    # DNS (Stage 14, ADR 032)
    "notify_config.type.track_dns": "Track DNS",
    "notify_config.type.dns_a_change": "A records change",
    "notify_config.type.dns_aaaa_change": "AAAA records change",
    "notify_config.type.dns_ns_change": "NS change (including WHOIS mismatch)",
    "notify_config.type.dns_unreachable": "DNS unreachable",
    # Email-intel (ADR 036)
    "notify_config.type.track_email": "Email monitoring",
    "notify_config.type.email_change": "Email records change (MX/SPF/DMARC/DKIM)",
    "notify_config.type.email_mx": "MX records change",
    "notify_config.type.email_spf": "SPF change",
    "notify_config.type.email_dmarc": "DMARC change",
    "notify_config.type.email_dkim": "DKIM change",
    # Subdomain monitoring (TASK-0029, ADR 038)
    "notify_config.type.track_subdomains": "Subdomain monitoring",
    "notify_config.type.subdomain_new": "New subdomains",
    "notify_config.type.subdomain_removed": "Removed subdomains",
    "notify_config.edit_subdomain_interval": "🌐 Change subdomain check interval",
    "notify_config.subdomain_interval_prompt": (
        "Enter subdomain check interval (days). "
        "Minimum is 1 day.\n\n"
        "/default — use global settings (7 days)\n"
        "/cancel — keep current"
    ),
    "notify_config.subdomain_interval_saved_override": "✅ Subdomain interval: every {days} day(s)",
    "notify_config.subdomain_interval_saved_default": "✅ Subdomains: reverted to global settings",
    "notify_config.subdomain_interval_invalid": (
        "❌ Invalid format. Type an integer from 1 to 365 (e.g. <code>7</code>)."
    ),
    "button.privacy": "📜 Privacy policy",
    "button.github": "💻 GitHub",
    "button.list_prev": "◀️ Prev",
    "button.list_next": "Next ▶️",
    "button.list_filter": "🔍 Filter",
    "button.list_csv": "📥 CSV",
    "button.filter_all": "All",
    "button.filter_expiring": "Expiring (<30 days)",
    "button.filter_no_data": "No data",
    "button.filter_muted": "Muted",
    "button.settings_timezone": "🌍 Timezone",
    "button.settings_time": "🕘 Time",
    "button.settings_days": "🔔 Reminder days",
    "button.settings_language": "🌐 Language",
    "button.tz_custom": "✏️ Enter manually",
    "button.days_standard": "Standard (30, 7, 1)",
    "button.days_often": "Often (60, 30, 14, 7, 3, 1)",
    "button.days_last": "Only one day before (1)",
    "button.days_custom": "✏️ Custom",
    "button.lang_ru": "🇷🇺 Русский",
    "button.lang_en": "🇬🇧 English",
    "button.confirm_yes": "✅ Yes",
    "button.confirm_no": "❌ Cancel",
    "button.delete": "🗑 Delete",
    "button.notify_settings": "⚙️ Notification settings",
    "button.wishlist_add": "🎯 Watch for drop",
    "button.wishlist_remove": "❌ Remove from wishlist",
    "button.download_add": "✅ Add {count}",
    "button.download_show_invalid": "📄 Show invalid",
    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------
    "errors.no_domain": "❌ Specify a domain. Example: /whois example.com",
    "errors.no_domain_with_list": (
        "❌ Specify a domain. Example: /unnotify example.com\nTo list your domains: /list"
    ),
    "errors.invalid_domain": "❌ Doesn't look like a domain. Example: example.com",
    "errors.public_suffix_not_domain": "❌ This is a public suffix (co.uk, .ru, etc.), not a domain.",
    "errors.not_in_list": "❌ This domain is not being tracked",
    "errors.limit_reached": (
        "❌ Reached the limit of {limit} domains. Remove unused ones via /rmv or /list."
    ),
    "errors.rate_limit": "❌ Too many requests. Try again in {seconds} sec.",
    "errors.rate_limit_add": (
        "❌ Too many requests. Try again in {minutes} minutes or use /download."
    ),
    "errors.force_refresh_cooldown": (
        "⏱ This domain can be manually refreshed once every {hours} hours. "
        "Automatic checks run on schedule."
    ),
    "errors.whois_unavailable": "❌ Could not fetch data. Try again later.",
    "errors.whois_failed": "❌ Could not check {domain}: {reason}",
    "errors.whois_stale": "⚠️ Data may be stale (last updated {days} day(s) ago)",
    "errors.invalid_timezone": "❌ Couldn't recognize the timezone. Example: Europe/Moscow",
    "errors.invalid_notify_days": (
        "❌ Couldn't parse. Enter days separated by space or comma, e.g.: 30 7 1"
    ),
    "errors.blocked": "❌ Access to the bot is restricted.",
    # ------------------------------------------------------------------
    # Stubs (stages 3-4)
    # ------------------------------------------------------------------
    "stubs.coming_soon": (
        "🛠 The {command} command is temporarily unavailable.\n"
        "WHOIS functionality is coming in the next bot updates."
    ),
    "stubs.coming_soon_download": (
        "🛠 Bulk import is temporarily unavailable.\n"
        "It will be available once WHOIS logic is wired in."
    ),
    "stubs.coming_soon_text": (
        "💡 Looks like a domain, but WHOIS logic isn't wired in yet.\n"
        "Use /help to see available commands."
    ),
    # ------------------------------------------------------------------
    # /add
    # ------------------------------------------------------------------
    "commands.add.success": (
        "✅ {domain} is now being tracked\n"
        "\n"
        "📅 Expires: {expires} ({days_left})\n"
        "🏢 Registrar: {registrar}\n"
        "🔔 I'll remind you {notify_days} before"
    ),
    "commands.add.success_no_data": (
        "✅ {domain} is now being tracked\n"
        "\n"
        "Fetching WHOIS data, I'll send the result in a minute."
    ),
    "commands.add.promoted_from_wishlist": "✅ {domain} moved from wishlist to regular tracking",
    "commands.add.already_tracked": "ℹ️ {domain} is already in your list",
    "commands.add.subdomain_added": "✅ {domain} added (subdomain of {parent})",
    # ------------------------------------------------------------------
    # /rmv
    # ------------------------------------------------------------------
    "commands.rmv.success": "🗑 {domain} removed from your list",
    "commands.rmv.not_found": "❌ This domain is not being tracked",
    # ------------------------------------------------------------------
    # /list
    # ------------------------------------------------------------------
    "commands.list.header": "📋 Your domains ({total})\n\nPage {page}/{total_pages}",
    "commands.list.empty": "You have no domains yet. Use /add to add one.",
    # ------------------------------------------------------------------
    # /notify, /unnotify
    # ------------------------------------------------------------------
    "commands.notify.success": (
        "🔔 Notifications for {domain} enabled\nI'll remind you {notify_days} before expiry."
    ),
    "commands.unnotify.success": (
        "🔕 Notifications for {domain} disabled\n"
        "The domain stays in your list, no reminders will be sent."
    ),
    # ------------------------------------------------------------------
    # /delete_me
    # ------------------------------------------------------------------
    "commands.delete_me.warning": (
        "⚠️ Delete all data\n"
        "\n"
        "This will delete:\n"
        "• Your profile and settings\n"
        "• {domains_count} tracked domains\n"
        "• Notification history\n"
        "\n"
        "This cannot be undone. To confirm, send:\n"
        "/delete_me_confirm"
    ),
    "commands.delete_me.need_init": "Use /delete_me first",
    "commands.delete_me.success": (
        "✅ All your data has been deleted.\n"
        "If you ever come back — just type /start.\n"
        "Thanks for using the bot!"
    ),
    # ------------------------------------------------------------------
    # /whois — domain card
    # ------------------------------------------------------------------
    "commands.whois.section_expiry": "📅 Expiry",
    "commands.whois.line_registered": "Registered: {date}",
    "commands.whois.line_expires": "Expires: {date} ({days_until})",
    "commands.whois.line_expires_hidden": "expiry date hidden by registry (DENIC etc.)",
    "commands.whois.line_updated": "Updated: {date}",
    "commands.whois.line_registrar": "🏢 Registrar: {registrar}",
    "commands.whois.line_owner": "👤 Owner: {owner}",
    "commands.whois.owner_org": "{org} ({country})",
    "commands.whois.owner_org_no_country": "{org}",
    "commands.whois.owner_name": "{name} ({country})",
    "commands.whois.owner_name_no_country": "{name}",
    "commands.whois.owner_redacted_private": "Private individual (hidden)",
    "commands.whois.owner_redacted_privacy": "Hidden (privacy protected)",
    "commands.whois.section_status": "🔧 Statuses:",
    "commands.whois.section_ns": "🌍 Nameservers:",
    # SSL (Stage 12, ADR 030)
    "commands.whois.ssl_section": "🔒 SSL certificate:",
    "commands.whois.ssl_line_expires": "{emoji} Valid until: {date} ({days_until})",
    "commands.whois.ssl_line_issuer": "Issuer: {issuer}",
    "commands.whois.ssl_unreachable": "🔒 SSL certificate: ⚠️ HTTPS endpoint is down",
    # DNS (Stage 14, ADR 032)
    "commands.whois.dns_section": "🌐 <b>DNS</b>",
    "commands.whois.dns_line_a": "A: {records}",
    "commands.whois.dns_line_aaaa": "AAAA: {records}",
    "commands.whois.dns_line_ns_ok": "NS: {records} ✓",
    "commands.whois.dns_line_ns_mismatch": "NS: {records} 🚨",
    "commands.whois.dns_line_ns_registry": "Registry: {records}",
    "commands.whois.dns_unreachable": "🌐 <b>DNS</b>: ⚠️ unreachable",
    "commands.whois.dns_mx_only": "🌐 <b>DNS</b>: MX only (email-only domain)",
    "commands.whois.dns_no_dns": "🌐 <b>DNS</b>: no records",
    # Background delivery of /whois card updates (TASK-0076)
    "tasks.deliver.dns_update": "🌐 <b>DNS · {domain}</b> (update):",
    "tasks.deliver.ssl_update": "🔒 <b>SSL · {domain}</b> (update):",
    "tasks.deliver.email_update": "📧 <b>Email · {domain}</b> (update):",
    # On-demand failure delivery (TASK-0086) — never fail silently
    "tasks.deliver.failed.subdomains": (
        "⚠️ Could not fetch subdomains for <b>{domain}</b> — "
        "the data source (crt.sh) is unavailable. Please try again later."
    ),
    "tasks.deliver.failed.email_deep": (
        "⚠️ Deep e-mail analysis failed for <b>{domain}</b> — "
        "DNS queries did not go through. Please try again later."
    ),
    "tasks.deliver.failed.email": (
        "⚠️ Could not refresh email records for <b>{domain}</b>. Please try again later."
    ),
    "tasks.deliver.failed.dns": (
        "⚠️ Could not refresh DNS for <b>{domain}</b>. Please try again later."
    ),
    "tasks.deliver.failed.ssl": (
        "⚠️ Could not check the SSL certificate for <b>{domain}</b>. Please try again later."
    ),
    # Email-intel (TASK-0018, ADR 036)
    "commands.whois.email_section": "📧 <b>Email</b>",
    "commands.whois.email_unreachable": "📧 <b>Email</b>: ⚠️ unreachable",
    "commands.whois.email_line_mx": "MX: {records}",
    "commands.whois.email_no_mx": "MX: not configured",
    "commands.whois.email_line_spf": "SPF: {mode}",
    "commands.whois.email_no_spf": "SPF: not configured",
    "commands.whois.email_spf_mode.fail": "strict",
    "commands.whois.email_spf_mode.softfail": "soft",
    "commands.whois.email_spf_mode.neutral": "neutral (?all)",
    "commands.whois.email_spf_mode.pass": "allow all (+all) ⚠️",
    "commands.whois.email_spf_mode.none": "no record",
    "commands.whois.email_line_dmarc": "DMARC: {policy}",
    "commands.whois.email_no_dmarc": "DMARC: not configured",
    "commands.whois.email_dmarc_none_compact": "none",
    "commands.whois.email_dmarc_policy.none": "none",
    "commands.whois.email_dmarc_policy.quarantine": "quarantine",
    "commands.whois.email_dmarc_policy.reject": "reject",
    "commands.whois.email_line_dkim": "DKIM: {selectors}",
    # TASK-0040 (ADR 040): compact inline + pending placeholder
    "commands.whois.email_compact_status": "SPF: {spf} · DMARC: {dmarc}",
    "commands.whois.pending_collect": "⏳ Collecting {section}… Tap 🔄 Refresh in a few seconds",
    "commands.whois.source_just_now": "ℹ️ Fetched: just now",
    "commands.whois.source_cached": "ℹ️ From cache, updated {ago}",
    "commands.whois.free": "🌐 {domain} — not registered\n\nThe domain is available for registration.",
    # TASK-0092: WHOIS says free, but RDAP confirmation could not be obtained
    "commands.whois.free_unverified": (
        "🌐 {domain} — no WHOIS record found\n\n"
        "The domain appears to be available, but this could not be confirmed "
        "via a second source (RDAP). If it was registered recently, registry "
        "data may not have propagated yet. Re-check later: /check {domain}"
    ),
    "commands.whois.subdomain_banner": "🔎 {subdomain} — subdomain of {parent}\n\nWHOIS is shown for the parent domain.",
    # ------------------------------------------------------------------
    # /list — row template
    # ------------------------------------------------------------------
    "commands.list.row_known": "{emoji} {subdomain_mark}{domain} — {days_until} ({date}){muted}",
    "commands.list.row_unknown": "{emoji} {subdomain_mark}{domain} — no data{muted}",
    "commands.list.row_expiry_hidden": "{emoji} {subdomain_mark}{domain} — expiry date hidden by registry{muted}",
    "commands.list.row_wishlist": "🎯 {domain} — waiting for it to drop",
    "commands.list.muted_suffix": " 🔕",
    "commands.list.unknown_value": "—",
    # Stage 9 — search/filters/wishlist
    "list.search.placeholder": "🔍 Search",
    "list.search.prompt": "Type a substring to search or /cancel",
    "list.search.current": "🔍 Search: <code>{query}</code>",
    "list.search.clear": "❌ Clear search",
    "list.search.empty": "Nothing found for <code>{query}</code>.",
    "list.filter.critical": "🚨 With problems",
    "list.filter.expired": "💀 Expired",
    # ------------------------------------------------------------------
    # /stats
    # ------------------------------------------------------------------
    "commands.stats.body": (
        "📊 Your statistics\n"
        "\n"
        "Total domains: {total}\n"
        "├ With data: {with_data}\n"
        "└ Without data: {without_data}\n"
        "\n"
        "Expiring:\n"
        "├ In 7 days: {exp_7}\n"
        "├ In 30 days: {exp_30}\n"
        "└ In 90 days: {exp_90}\n"
        "\n"
        "🔕 Muted: {muted}\n"
        "📅 Added this month: {added_month}"
    ),
    # ------------------------------------------------------------------
    # /settings
    # ------------------------------------------------------------------
    "commands.settings.menu": (
        "⚙️ Settings\n"
        "\n"
        "🌍 Timezone: {timezone}\n"
        "🕘 Reminder time: {hour:02d}:00\n"
        "🔔 Reminder days: {notify_days}\n"
        "🌐 Language: {language}"
    ),
    "commands.settings.choose_timezone": "Pick a timezone or enter one manually:",
    "commands.settings.tz_prompt_manual": (
        "Enter an IANA timezone name (e.g. Europe/Moscow). Or /cancel to abort."
    ),
    "commands.settings.tz_saved": "✅ Timezone saved: {timezone}",
    "commands.settings.choose_time": "Pick the hour to send reminders at:",
    "commands.settings.time_saved": "✅ Reminder time: {hour:02d}:00",
    "commands.settings.choose_days": (
        "How many days before expiry to remind? Pick a preset or enter your own:"
    ),
    "commands.settings.days_prompt_custom": (
        "Enter days separated by space or comma, e.g.: 60 30 14 7 3 1\nOr /cancel to abort."
    ),
    "commands.settings.days_saved": "✅ Reminder days: {notify_days}",
    "commands.settings.choose_language": "Pick a language:",
    "commands.settings.language_saved": "✅ Language saved: {language}",
    "commands.settings.lang_ru_name": "Русский",
    "commands.settings.lang_en_name": "English",
    # ------------------------------------------------------------------
    # /csv
    # ------------------------------------------------------------------
    "csv.empty": "You have no domains to export.",
    "csv.generating": "Generating a file with {count} domains…",
    "csv.ready": "File ready: {count} domains",
    # ------------------------------------------------------------------
    # /download
    # ------------------------------------------------------------------
    "download.intro": (
        "📥 Bulk import\n"
        "\n"
        "Send a TXT or CSV file with a list of domains "
        "(one per line, or in the first column).\n"
        "\n"
        "Limit: {limit} domains per import. Use /cancel to abort."
    ),
    "download.cancel": "Import cancelled.",
    "download.timeout": "Timed out, please start /download again.",
    "download.no_file": "Send a file or /cancel.",
    "download.too_large": "❌ File too large, maximum {max_mb} MB.",
    "download.parse_failed": "❌ Could not parse the file.",
    "download.rate_limit": "❌ You can run import at most {limit} times per day.",
    "download.preview": (
        "📋 Found {total} domains\n"
        "\n"
        "✅ Valid and new: {new}\n"
        "⚠️ Already tracked: {already}\n"
        "❌ Invalid: {invalid}"
    ),
    "download.preview_truncated": (
        "\n\n⚠️ The {limit} domains per import limit was hit. " "The rest of the file was ignored."
    ),
    "download.confirm_button": "✅ Add {count}",
    "download.cancel_button": "❌ Cancel",
    "download.success": (
        "✅ Added {count} domains.\n"
        "Data is being fetched in the background, check /list in a few minutes."
    ),
    "download.limit_exceeded": (
        "⚠️ Only {fits} of {requested} fit — your limit is {limit} domains.\n"
        "Remove unused ones via /rmv or /list."
    ),
    "download.nothing_to_add": "All domains from the file are already tracked.",
    # ------------------------------------------------------------------
    # /admin
    # ------------------------------------------------------------------
    "admin.forbidden": "❌ Admin command — access denied.",
    "admin.stats": (
        "📊 System status\n"
        "\n"
        "👤 Users: {users}\n"
        "🌐 Cached domains: {cached_domains}\n"
        "📌 Subscriptions (user_domains): {tracked}\n"
        "⏳ Pending checks: {due_checks}"
    ),
    "admin.alert_sent": "✅ Alert sent.",
    "admin.alert_no_text": "Usage: /admin alert <text>",
    "admin.alert_no_channel": "❌ ADMIN_CHANNEL_ID is not configured.",
    "admin.unknown": (
        "Available commands:\n"
        "/admin stats — current statistics\n"
        "/admin alert <text> — test channel alert"
    ),
    # ------------------------------------------------------------------
    # /download (legacy keys used by the stub)
    # ------------------------------------------------------------------
    "commands.download.prompt": (
        "📥 Bulk import\n"
        "\n"
        "Send a TXT or CSV file with a list of domains "
        "(one per line, or in the first column).\n"
        "\n"
        "Limit: {limit} domains per import."
    ),
    "commands.download.send_file_or_cancel": "Send a file or /cancel",
    "commands.download.parse_failed": "❌ Could not parse the file.",
    "commands.download.preview": (
        "📋 Found {total} domains\n"
        "\n"
        "✅ Valid and new: {new}\n"
        "⚠️ Already tracked: {already}\n"
        "❌ Invalid: {invalid}"
    ),
    "commands.download.done": (
        "✅ Added {count} domains.\n"
        "Data is being fetched in the background, check /list in a few minutes."
    ),
    # ------------------------------------------------------------------
    # Notifications (Stage 5)
    # ------------------------------------------------------------------
    "notifications.expiry.title": "⏰ Registration expires soon",
    "notifications.expiry.body": (
        "⏰ <b>{domain}</b>\n"
        "\n"
        "📅 Expires: {expires_at} (in {days_left})\n"
        "🏢 Registrar: {registrar}\n"
        "\n"
        "Don't forget to renew."
    ),
    "notifications.expiry.button_renewed": "✅ Already renewed",
    "notifications.expiry.button_mute": "🔕 Stop reminders for this domain",
    "notifications.change.registrar": (
        "🏢 <b>{domain}</b> — registrar changed\n\nWas: {old}\nNow: {new}"
    ),
    "notifications.change.ns": (
        "🌍 <b>{domain}</b> — NS servers changed\n\nWas: {old}\nNow: {new}"
    ),
    "notifications.change.status": (
        "🔧 <b>{domain}</b> — statuses changed\n\nWas: {old}\nNow: {new}"
    ),
    "notifications.change.expires_at": (
        "📅 <b>{domain}</b> — expiry date changed\n\nWas: {old}\nNow: {new}"
    ),
    "notifications.change.registrant": (
        "👤 <b>{domain}</b> — owner changed\n\nWas: {old}\nNow: {new}"
    ),
    "notifications.change.privacy_revealed": (
        "👤 <b>{domain}</b> — owner data revealed\n\nNow: {new}"
    ),
    "notifications.change.privacy_hidden": ("👤 <b>{domain}</b> — owner data hidden\n\nWas: {old}"),
    "notifications.change.button_open": "🌐 Open domain",
    "notifications.change.unknown": "—",
    "notifications.problem.title": "⚠️ Can't check {domain}",
    "notifications.problem.body": (
        "⚠️ <b>{domain}</b>\n"
        "\n"
        "Can't refresh WHOIS data.\n"
        "Last successful check: {last_ok}\n"
        "Last known expiry: {expires_at}\n"
        "\n"
        "Try manually or verify that the domain is still active."
    ),
    "notifications.problem.button_retry": "🔄 Retry now",
    "notifications.problem.button_mute": "🔕 Mute problem alerts",
    # ------------------------------------------------------------------
    # SSL notifications (Stage 12, ADR 030)
    # ------------------------------------------------------------------
    "notifications.ssl_expiry.body": (
        "🔒 <b>{domain}</b> — SSL certificate expires soon\n"
        "\n"
        "📅 Valid until: {not_after} ({days_left})\n"
        "🏛️ Issuer: {issuer}\n"
        "\n"
        "If you rely on auto-renewal, double-check that it's working."
    ),
    "notifications.ssl_expiry.button_renewed": "✅ Renewed",
    "notifications.ssl_expiry.button_mute": "🔕 Mute SSL alerts for this domain",
    "notifications.ssl_change.issuer": ("🏛️ <b>{domain}</b> — SSL issuer changed\n\nNow: {issuer}"),
    "notifications.ssl_change.not_after": (
        "🔒 <b>{domain}</b> — SSL certificate was renewed\n\nNew expiry: {not_after}"
    ),
    "notifications.ssl_change.unreachable": (
        "⚠️ <b>{domain}</b> — HTTPS endpoint is down\n\n"
        "The site stopped serving an SSL certificate. Check that the web server is running."
    ),
    "notifications.ssl_change.reachable": ("✅ <b>{domain}</b> — HTTPS is back online"),
    # DNS (Stage 14, ADR 032)
    "notifications.dns_change.a_changed": (
        "🟠 <b>{domain}</b> — A records changed\n\nNow: {records}"
    ),
    "notifications.dns_change.aaaa_changed": (
        "🟠 <b>{domain}</b> — AAAA records changed\n\nNow: {records}"
    ),
    "notifications.dns_change.ns_changed": (
        "🟠 <b>{domain}</b> — NS servers changed\n\nNow: {records}"
    ),
    "notifications.dns_change.ns_mismatch_detected": (
        "🚨 <b>CRITICAL: {domain}</b>\n\n"
        "DNS returns NS servers different from registry (WHOIS). "
        "This is a classic indicator of domain hijack or incomplete "
        "DNS migration. Check /whois and verify that registry NS "
        "records match your expectations.\n\n"
        "DNS-NS: {records}"
    ),
    "notifications.dns_change.ns_mismatch_resolved": (
        "✅ <b>{domain}</b> — DNS-NS / registry-NS mismatch resolved"
    ),
    "notifications.dns_change.unreachable": (
        "🚨 <b>{domain}</b> — DNS stopped responding\n\n"
        "The domain may be expired, deleted, or temporarily unavailable. "
        "If you didn't make changes — this is urgent."
    ),
    "notifications.dns_change.reachable": ("✅ <b>{domain}</b> — DNS is back online"),
    # Email-intel (ADR 036)
    "notifications.email_change.mx": (
        "📧 <b>{domain}</b> — MX records changed\n\n"
        "The list of mail servers has changed. Verify that the changes are expected."
    ),
    "notifications.email_change.spf": (
        "📧 <b>{domain}</b> — SPF record changed\n\n"
        "SPF policy has changed. Verify that the changes are expected."
    ),
    "notifications.email_change.dmarc": (
        "📧 <b>{domain}</b> — DMARC changed\n\n"
        "DMARC policy has changed. Verify that the changes are expected."
    ),
    "notifications.email_change.dkim": (
        "📧 <b>{domain}</b> — DKIM selectors changed\n\n"
        "The list of DKIM selectors has changed. Verify that the changes are expected."
    ),
    "notifications.email_change.unreachable": (
        "⚠️ <b>{domain}</b> — DNS for email records unreachable\n\n"
        "Cannot resolve MX/SPF/DMARC. Domain may be expired or deleted."
    ),
    "notifications.email_change.reachable": ("✅ <b>{domain}</b> — email records back online"),
    # Subdomain monitoring (TASK-0029, ADR 038)
    "notifications.subdomain.new_header": "🆕 New subdomains detected:",
    "notifications.subdomain.removed_header": "➖ Removed subdomains:",
    "notifications.subdomain.and_more": "… and {count} more",
    "notifications.ack.muted": "🔕 Notifications for this domain are off",
    "notifications.ack.refresh_started": "🔄 Refresh started",
    "notifications.ack.no_access": "❌ This domain isn't in your list",
    "notifications.value.unknown": "—",
    "notifications.value.never": "never",
    "notifications.wishlist.available.title": "🎉 <b>{domain}</b> is now available!",
    "notifications.wishlist.available.body": (
        "You can register it through any registrar.\n\n"
        "<i>Remember: automated drop-catchers may be faster than manual "
        "registration for popular domains.</i>"
    ),
    "notifications.wishlist.available.button_track": "📌 Start tracking",
    "notifications.wishlist.available.button_dismiss": "OK",
    "notify.on": "🔔 Notifications for {domain} enabled",
    "notify.off": "🔕 Notifications for {domain} disabled",
    # Stage 9 — /wishlist
    "commands.wishlist.empty": (
        "🎯 Wishlist is empty.\n\nAdd a domain with /wishlist <code>example.com</code> "
        "or the «Watch for drop» button in a /whois card."
    ),
    "commands.wishlist.header": "🎯 Your wishlist ({total})\n\nPage {page}/{total_pages}",
    "commands.wishlist.added": (
        "🎯 <b>{domain}</b> added to wishlist.\n" "I'll send one alert when it becomes available."
    ),
    "commands.wishlist.tracked_now": (
        "✅ <b>{domain}</b> is now in your normal /list. Good luck with registration!"
    ),
    "commands.wishlist.already_added": (
        "⚠️ <b>{domain}</b> is already in wishlist. "
        "You'll be notified when the domain becomes available."
    ),
    "commands.wishlist.removed": "🎯 <b>{domain}</b> removed from wishlist.",
    "commands.wishlist.not_found": "⚠️ Domain not found in wishlist.",
    # ------------------------------------------------------------------
    # Subdomain enumeration (Stage 18, ADR 037)
    # ------------------------------------------------------------------
    "commands.subdomains.searching": (
        "🔍 Searching subdomains for <b>{domain}</b>...\n\n"
        "Request to crt.sh may take time. I'll send the result separately."
    ),
    "commands.subdomains.header": (
        "🔍 Subdomains of <b>{domain}</b>\n\n" "Found: {count}\n" "Updated: {fetched_at}"
    ),
    "commands.subdomains.list_item": "• {subdomain}",
    "commands.subdomains.empty": (
        "🔍 Subdomains of <b>{domain}</b>\n\n" "Nothing found yet. Try again later."
    ),
    "commands.subdomains.no_cache": (
        "🔍 Subdomains of <b>{domain}</b>\n\n" "Cache is empty or stale. Try the command later."
    ),
    "commands.subdomains.unavailable": (
        "⚠️ Couldn't get subdomains for <b>{domain}</b>\n\n"
        "crt.sh is temporarily unavailable. Try again later."
    ),
    "commands.subdomains.invalid_domain": "❌ Invalid domain",
    "commands.subdomains.public_suffix": "❌ This is a public suffix, not a domain",
    "commands.subdomains.button_track": "📌 Track",
    "commands.subdomains.button_track_all": "📌 Track all",
    "commands.subdomains.button_refresh": "🔄 Refresh",
    "commands.subdomains.too_many": (
        "⚠️ Found {count} subdomains.\n\n"
        "Display limit: {max}.\n"
        "Try selecting a specific subdomain or use a filter."
    ),
    "commands.subdomains.track_all_result": (
        "✅ Added: {added}\n" "⏭ Already tracked: {skipped}\n" "{errors_msg}"
    ),
    "commands.subdomains.track_all_result_errors": "❌ Errors: {errors}",
    # ------------------------------------------------------------------
    # Inline buttons from the welcome screen (start_keyboard callbacks)
    # ------------------------------------------------------------------
    "start.check_prompt": (
        "🌐 Send a domain as a message — I'll show its WHOIS.\n"
        "Or use the command: /whois example.com"
    ),
    # ------------------------------------------------------------------
    # WebApp (mini-app, ADR 043)
    # ------------------------------------------------------------------
    "webapp.open_prompt": (
        "📱 Portfolio dashboard: domain health, expiry calendar, "
        "alerts and groups — via the button below."
    ),
}
