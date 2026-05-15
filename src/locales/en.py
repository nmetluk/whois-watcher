"""English locale. Mirrors the keys in ``ru.py``.

If a key is missing here, the locale resolver falls back to ``ru``.
"""

from __future__ import annotations

LOCALE: dict[str, str] = {
    # ------------------------------------------------------------------
    # /start, /help
    # ------------------------------------------------------------------
    "start.greeting": (
        "👋 Hi! I track your domains and remind you about registration expiry.\n"
        "\n"
        "🔧 What I can do:\n"
        "/whois <domain> — check WHOIS\n"
        "/add <domain> — add to tracking\n"
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
    "help.title": "📖 Help",
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
    "button.privacy": "📜 Privacy policy",
    "button.github": "💻 GitHub",
    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------
    "errors.no_domain": "❌ Specify a domain. Example: /whois example.com",
    "errors.no_domain_with_list": (
        "❌ Specify a domain. Example: /unnotify example.com\n" "To list your domains: /list"
    ),
    "errors.invalid_domain": "❌ Doesn't look like a domain. Example: example.com",
    "errors.not_in_list": "❌ This domain is not being tracked",
    "errors.limit_reached": (
        "❌ Reached the limit of {limit} domains. " "Remove unused ones via /rmv or /list."
    ),
    "errors.rate_limit": "❌ Too many requests. Try again in {minutes} minutes.",
    "errors.rate_limit_add": (
        "❌ Too many requests. Try again in {minutes} minutes " "or use /download."
    ),
    "errors.force_refresh_cooldown": (
        "⏱ This domain can be manually refreshed once every {hours} hours. "
        "Automatic checks run on schedule."
    ),
    "errors.whois_unavailable": "❌ Could not fetch data. Try again later.",
    "errors.whois_stale": ("⚠️ Data may be stale (last updated {days} day(s) ago)"),
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
        "🔔 Notifications for {domain} enabled\n" "I'll remind you {notify_days} before expiry."
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
    # /whois — free domain
    # ------------------------------------------------------------------
    "commands.whois.free": (
        "🌐 {domain} — not registered\n" "\n" "The domain is available for registration."
    ),
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
