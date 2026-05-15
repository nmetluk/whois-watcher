"""English locale. Mirrors the keys in ``ru.py``.

If a key is missing here, the locale resolver falls back to ``ru``.
"""

from __future__ import annotations

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
    # Inline buttons
    # ------------------------------------------------------------------
    "button.check_domain": "🌐 Check domain",
    "button.my_domains": "📋 My domains",
    "button.settings": "⚙️ Settings",
    "button.follow": "👁 Track",
    "button.unfollow": "🗑 Stop tracking",
    "button.refresh": "🔄 Refresh",
    "button.raw": "📄 Raw response",
    "button.notify_on": "🔔 Turn back on",
    "button.cancel": "❌ Cancel",
    "button.back": "◀️ Back",
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
    "commands.add.already_tracked": "ℹ️ {domain} is already in your list",
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
    "commands.whois.line_updated": "Updated: {date}",
    "commands.whois.line_registrar": "🏢 Registrar: {registrar}",
    "commands.whois.section_status": "🔧 Statuses:",
    "commands.whois.section_ns": "🌍 Nameservers:",
    "commands.whois.source_just_now": "ℹ️ Fetched: just now",
    "commands.whois.source_cached": "ℹ️ From cache, updated {ago}",
    "commands.whois.free": "🌐 {domain} — not registered\n\nThe domain is available for registration.",
    # ------------------------------------------------------------------
    # /list — row template
    # ------------------------------------------------------------------
    "commands.list.row_known": "{emoji} {domain} — {days_until} ({date}){muted}",
    "commands.list.row_unknown": "{emoji} {domain} — no data{muted}",
    "commands.list.muted_suffix": " 🔕",
    "commands.list.unknown_value": "—",
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
    # /download
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
}
