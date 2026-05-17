"""Русская локаль. Ключи — `dot.case.path`.

Все пользовательские тексты бота — отсюда. Не хардкодить строки в хэндлерах.
Тон умеренный, эмодзи только как индикаторы статусов (ADR 021).
"""

from __future__ import annotations

from typing import Literal

# Severity статуса домена — определяет цвет/эмодзи в карточке и сортировку.
StatusSeverity = Literal["normal", "info", "warning", "critical"]


# Перевод WHOIS-статусов: код → (severity, человеческий текст, emoji_override).
# ``emoji_override=None`` → форматтер использует дефолтный эмодзи по severity.
#
# Перекрывает три семейства:
#   • EPP (RFC 5731) gTLD-статусы — самая частая категория
#   • TCINET (.ru / .рф) — английскими словами, но другой набор
#   • DENIC (.de), AFNIC (.fr) — нестандартные служебные ярлыки
WHOIS_STATUSES: dict[str, tuple[StatusSeverity, str, str | None]] = {
    # ---- EPP gTLD -----------------------------------------------------
    "ok": ("normal", "Активен", "🟢"),
    "active": ("normal", "Активен", "🟢"),
    "inactive": ("warning", "Не активен", "🟡"),
    "clientTransferProhibited": ("info", "Защищён от трансфера", "🔒"),
    "clientUpdateProhibited": ("info", "Защищён от изменений", "🔒"),
    "clientDeleteProhibited": ("info", "Защищён от удаления", "🔒"),
    "clientHold": ("critical", "Заблокирован регистратором", "🚨"),
    "clientRenewProhibited": ("info", "Защищён от автопродления", "🔒"),
    "serverTransferProhibited": ("info", "Защищён от трансфера (реестр)", "🔒"),
    "serverUpdateProhibited": ("info", "Защищён реестром от изменений", "🔒"),
    "serverDeleteProhibited": ("info", "Защищён реестром от удаления", "🔒"),
    "serverRenewProhibited": ("info", "Реестр запрещает продление", "🔒"),
    "serverHold": ("critical", "Заблокирован реестром", "🚨"),
    "pendingCreate": ("info", "Регистрация в процессе", "🕘"),
    "pendingDelete": ("critical", "Скоро будет удалён", "⏳"),
    "pendingTransfer": ("warning", "В процессе трансфера", "🔄"),
    "pendingUpdate": ("info", "В процессе изменения", "🕘"),
    "pendingRenew": ("info", "В процессе продления", "🕘"),
    "pendingRestore": ("warning", "В процессе восстановления", "🔄"),
    "redemptionPeriod": ("warning", "В периоде восстановления", "⚠️"),
    "addPeriod": ("info", "Период добавления", "📅"),
    "autoRenewPeriod": ("info", "Период автопродления", "📅"),
    "renewPeriod": ("info", "Период продления", "📅"),
    "transferPeriod": ("info", "Период трансфера", "📅"),
    # ---- TCINET (.ru / .рф / .su) ------------------------------------
    "REGISTERED": ("normal", "Зарегистрирован", None),
    "DELEGATED": ("normal", "Делегирован", None),
    "VERIFIED": ("normal", "Верифицирован", None),
    "NOT DELEGATED": ("warning", "Не делегирован", "⚠️"),
    "BLOCKED": ("critical", "Заблокирован", "🚨"),
    # ---- DENIC (.de) -------------------------------------------------
    "connect": ("normal", "Подключён", "🟢"),
    "failed": ("critical", "Ошибка делегирования", "🚨"),
    "free": ("info", "Свободен", None),
    # ---- AFNIC (.fr) -------------------------------------------------
    "ACTIVE": ("normal", "Активен", "🟢"),
    "REDEMPTION": ("warning", "В периоде восстановления", "⚠️"),
    "FROZEN": ("warning", "Заморожен", "⚠️"),
}


LOCALE: dict[str, str] = {
    # ------------------------------------------------------------------
    # /start, /help, /cancel
    # ------------------------------------------------------------------
    "start.greeting": (
        "👋 Привет! Я слежу за вашими доменами и напоминаю об истечении регистрации.\n"
        "\n"
        "🔧 Что я умею:\n"
        "/whois &lt;домен&gt; — проверить WHOIS\n"
        "/add &lt;домен&gt; — добавить на слежение\n"
        "/list — список ваших доменов\n"
        "/csv — экспорт в CSV\n"
        "/download — массовый импорт\n"
        "/settings — настройки\n"
        "/help — полная справка\n"
        "\n"
        "💡 Можно просто прислать мне домен — покажу WHOIS.\n"
        "\n"
        "🆓 Сервис полностью бесплатный."
    ),
    "help.body": (
        "📖 <b>Справка</b>\n"
        "\n"
        "<b>Проверка домена</b>\n"
        "/whois &lt;домен&gt; — показать WHOIS\n"
        "/check &lt;домен&gt; — принудительная проверка (раз в сутки)\n"
        "\n"
        "<b>Слежение</b>\n"
        "/add &lt;домен&gt; — добавить домен\n"
        "/rmv &lt;домен&gt; — удалить домен\n"
        "/list — список доменов с пагинацией и фильтрами\n"
        "/notify &lt;домен&gt; — включить уведомления\n"
        "/unnotify &lt;домен&gt; — выключить уведомления\n"
        "\n"
        "<b>Импорт / экспорт</b>\n"
        "/csv — выгрузить ваш список в CSV\n"
        "/download — массовый импорт из TXT/CSV\n"
        "\n"
        "<b>Прочее</b>\n"
        "/settings — часовой пояс, время напоминаний, язык\n"
        "/stats — статистика по портфелю\n"
        "/cancel — отменить текущее действие\n"
        "/delete_me — удалить все данные\n"
        "\n"
        "💡 Просто пришлите домен — покажу WHOIS без команды."
    ),
    "cancel.done": "Действие отменено.",
    "cancel.nothing": "Нечего отменять.",
    # ------------------------------------------------------------------
    # Inline-кнопки
    # ------------------------------------------------------------------
    "button.check_domain": "🌐 Проверить домен",
    "button.my_domains": "📋 Мои домены",
    "button.settings": "⚙️ Настройки",
    "button.follow": "👁 Следить",
    "button.unfollow": "🗑 Снять со слежения",
    "button.refresh": "🔄 Обновить",
    "button.raw": "📄 Полный ответ",
    "button.notify_on": "🔔 Включить обратно",
    "button.cancel": "❌ Отмена",
    "button.back": "◀️ Назад",
    # Этап 11 — конфигуратор уведомлений
    "notify_config.button": "⚙️ Уведомления",
    "notify_config.title": "⚙️ <b>Настройки уведомлений</b> для {domain}",
    "notify_config.days_label_default": (
        "🔔 <b>Дни предупреждений:</b> {days}\n" "   <i>(используются глобальные настройки)</i>"
    ),
    "notify_config.days_label_custom": (
        "🔔 <b>Дни предупреждений:</b> {days}\n" "   <i>(per-domain override)</i>"
    ),
    "notify_config.types_label": "<b>Типы уведомлений:</b>",
    "notify_config.muted_yes": "🔇 <b>Полное отключение:</b> включено",
    "notify_config.muted_no": "🔇 <b>Полное отключение:</b> выключено",
    "notify_config.edit_days": "📅 Изменить дни предупреждений",
    "notify_config.mute_all": "🔇 Заглушить всё",
    "notify_config.unmute_all": "🔔 Снять заглушение",
    "notify_config.toggle.on": "✅",
    "notify_config.toggle.off": "❌",
    "notify_config.type.expiry": "Истечение срока",
    "notify_config.type.registrar_change": "Смена регистратора",
    "notify_config.type.ns_change": "Смена NS-серверов",
    "notify_config.type.status_change": "Смена статусов",
    "notify_config.type.registrant_change": "Смена владельца",
    "notify_config.type.problem": "Проблемы с проверкой",
    "notify_config.feedback_on": "✅ Включено: {type}",
    "notify_config.feedback_off": "❌ Отключено: {type}",
    "notify_config.feedback_muted": "🔇 Все уведомления заглушены",
    "notify_config.feedback_unmuted": "🔔 Заглушение снято",
    "notify_config.not_tracked": (
        "❌ Этот домен не отслеживается. Добавьте его через /add или кнопку «👁 Следить»."
    ),
    "notify_config.days_prompt": (
        "Введите дни через запятую (например: <code>60,30,14,7,3,1</code>).\n\n"
        "/default — использовать глобальные настройки\n"
        "/cancel — оставить как есть"
    ),
    "notify_config.days_invalid": (
        "❌ Неверный формат. Используйте числа через запятую (1–365, "
        "не более 10 значений). Например: <code>30,7,1</code>"
    ),
    "notify_config.days_saved_override": "✅ Сохранено: за {days}",
    "notify_config.days_saved_default": "✅ Возвращены глобальные настройки",
    "notify_config.days_unchanged": "Дни предупреждений оставлены без изменений.",
    # SSL (Этап 12, ADR 030)
    "notify_config.ssl_days_label_default": (
        "🔒 <b>SSL — дни предупреждений</b> (глобальные): за {days} дн. до истечения"
    ),
    "notify_config.ssl_days_label_custom": (
        "🔒 <b>SSL — дни предупреждений</b> (для домена): за {days} дн."
    ),
    "notify_config.edit_ssl_days": "🔒 Изменить дни SSL-предупреждений",
    "notify_config.ssl_days_prompt": (
        "Введите дни через запятую для SSL-сертификата (например: "
        "<code>14,7,3,1</code>).\n\n"
        "/default — использовать глобальные настройки\n"
        "/cancel — оставить как есть"
    ),
    "notify_config.ssl_days_saved_override": "✅ SSL-дни сохранены: за {days}",
    "notify_config.ssl_days_saved_default": "✅ SSL: возвращены глобальные настройки",
    "notify_config.type.track_ssl": "Мониторинг SSL",
    "notify_config.type.ssl_expiry": "Истечение SSL",
    "notify_config.type.ssl_change_issuer": "Смена SSL-сертификата",
    "button.privacy": "📜 Политика конфиденциальности",
    "button.github": "💻 GitHub",
    "button.list_prev": "◀️ Назад",
    "button.list_next": "Вперёд ▶️",
    "button.list_filter": "🔍 Фильтр",
    "button.list_csv": "📥 CSV",
    "button.filter_all": "Все",
    "button.filter_expiring": "Истекающие (<30 дней)",
    "button.filter_no_data": "Без данных",
    "button.filter_muted": "Без уведомлений",
    "button.settings_timezone": "🌍 Часовой пояс",
    "button.settings_time": "🕘 Время",
    "button.settings_days": "🔔 Дни напоминаний",
    "button.settings_language": "🌐 Язык",
    "button.tz_custom": "✏️ Ввести вручную",
    "button.days_standard": "Стандартно (30, 7, 1)",
    "button.days_often": "Часто (60, 30, 14, 7, 3, 1)",
    "button.days_last": "Только за день (1)",
    "button.days_custom": "✏️ Ввести свои",
    "button.lang_ru": "🇷🇺 Русский",
    "button.lang_en": "🇬🇧 English",
    "button.confirm_yes": "✅ Да",
    "button.confirm_no": "❌ Отмена",
    "button.delete": "🗑 Удалить",
    "button.notify_settings": "⚙️ Настроить уведомления",
    "button.wishlist_add": "🎯 Хочу когда освободится",
    "button.download_add": "✅ Добавить {count}",
    "button.download_show_invalid": "📄 Показать невалидные",
    # ------------------------------------------------------------------
    # Ошибки
    # ------------------------------------------------------------------
    "errors.no_domain": "❌ Укажите домен. Пример: /whois example.com",
    "errors.no_domain_with_list": (
        "❌ Укажите домен. Пример: /unnotify example.com\nЧтобы посмотреть домены: /list"
    ),
    "errors.invalid_domain": "❌ Не похоже на домен. Пример: example.com",
    "errors.not_in_list": "❌ Этот домен не отслеживается",
    "errors.limit_reached": (
        "❌ Достигнут лимит {limit} доменов. Удалите ненужные через /rmv или /list."
    ),
    "errors.rate_limit": "❌ Слишком много запросов. Попробуйте через {seconds} сек.",
    "errors.rate_limit_add": (
        "❌ Слишком много запросов. Попробуйте через {minutes} минут или используйте /download."
    ),
    "errors.force_refresh_cooldown": (
        "⏱ Этот домен можно обновить вручную раз в {hours} часа. "
        "Авто-проверка идёт по расписанию."
    ),
    "errors.whois_unavailable": "❌ Не удалось получить данные. Попробуйте позже.",
    "errors.whois_failed": "❌ Не удалось проверить {domain}: {reason}",
    "errors.whois_stale": "⚠️ Данные могут быть устаревшими (последнее обновление {days} дн. назад)",
    "errors.invalid_timezone": "❌ Не распознал часовой пояс. Пример: Europe/Moscow",
    "errors.invalid_notify_days": (
        "❌ Не понял формат. Введите дни через пробел или запятую, например: 30 7 1"
    ),
    "errors.blocked": "❌ Доступ к боту ограничен.",
    # ------------------------------------------------------------------
    # Заглушки (этапы 3-4)
    # ------------------------------------------------------------------
    "stubs.coming_soon": (
        "🛠 Команда {command} временно недоступна.\n"
        "WHOIS-логика появится в ближайших обновлениях бота."
    ),
    "stubs.coming_soon_download": (
        "🛠 Массовый импорт временно недоступен.\nПоявится после подключения WHOIS-логики."
    ),
    "stubs.coming_soon_text": (
        "💡 Похоже на домен, но WHOIS-логика ещё не подключена.\n"
        "Используйте /help, чтобы посмотреть доступные команды."
    ),
    # ------------------------------------------------------------------
    # /add
    # ------------------------------------------------------------------
    "commands.add.success": (
        "✅ {domain} добавлен на слежение\n"
        "\n"
        "📅 Истекает: {expires} ({days_left})\n"
        "🏢 Регистратор: {registrar}\n"
        "🔔 Уведомлю за {notify_days}"
    ),
    "commands.add.success_no_data": (
        "✅ {domain} добавлен на слежение\n"
        "\n"
        "Подгружаю WHOIS-данные, пришлю результат через минуту."
    ),
    "commands.add.already_tracked": "ℹ️ {domain} уже у вас в списке",
    # ------------------------------------------------------------------
    # /rmv
    # ------------------------------------------------------------------
    "commands.rmv.success": "🗑 {domain} удалён из вашего списка",
    "commands.rmv.not_found": "❌ Этот домен не отслеживается",
    # ------------------------------------------------------------------
    # /list
    # ------------------------------------------------------------------
    "commands.list.header": "📋 Ваши домены ({total})\n\nСтраница {page}/{total_pages}",
    "commands.list.empty": "У вас пока нет доменов. Используйте /add чтобы добавить.",
    # ------------------------------------------------------------------
    # /notify, /unnotify (ADR 015)
    # ------------------------------------------------------------------
    "commands.notify.success": (
        "🔔 Уведомления для {domain} включены\nНапомню за {notify_days} до истечения."
    ),
    "commands.unnotify.success": (
        "🔕 Уведомления для {domain} выключены\nДомен остаётся в списке, напоминаний не будет."
    ),
    # ------------------------------------------------------------------
    # /delete_me, /delete_me_confirm (ADR 017)
    # ------------------------------------------------------------------
    "commands.delete_me.warning": (
        "⚠️ Удаление всех данных\n"
        "\n"
        "Это удалит:\n"
        "• Ваш профиль и настройки\n"
        "• {domains_count} отслеживаемых доменов\n"
        "• Историю уведомлений\n"
        "\n"
        "Действие необратимо. Чтобы подтвердить, отправьте:\n"
        "/delete_me_confirm"
    ),
    "commands.delete_me.need_init": "Сначала используйте /delete_me",
    "commands.delete_me.success": (
        "✅ Все ваши данные удалены.\n"
        "Если захотите вернуться — просто напишите /start.\n"
        "Спасибо, что пользовались ботом!"
    ),
    # ------------------------------------------------------------------
    # /whois — карточка домена
    # ------------------------------------------------------------------
    "commands.whois.section_expiry": "📅 Срок действия",
    "commands.whois.line_registered": "Зарегистрирован: {date}",
    "commands.whois.line_expires": "Истекает: {date} ({days_until})",
    "commands.whois.line_updated": "Обновлён: {date}",
    "commands.whois.line_registrar": "🏢 Регистратор: {registrar}",
    "commands.whois.line_owner": "👤 Владелец: {owner}",
    "commands.whois.owner_org": "{org} ({country})",
    "commands.whois.owner_org_no_country": "{org}",
    "commands.whois.owner_name": "{name} ({country})",
    "commands.whois.owner_name_no_country": "{name}",
    "commands.whois.owner_redacted_private": "Скрыт (физ.лицо)",
    "commands.whois.owner_redacted_privacy": "Скрыт (приватность)",
    "commands.whois.section_status": "🔧 Статусы:",
    "commands.whois.section_ns": "🌍 NS-серверы:",
    # SSL (Этап 12, ADR 030)
    "commands.whois.ssl_section": "🔒 SSL-сертификат:",
    "commands.whois.ssl_line_expires": "{emoji} Действителен до: {date} ({days_until})",
    "commands.whois.ssl_line_issuer": "Издатель: {issuer}",
    "commands.whois.ssl_unreachable": "🔒 SSL-сертификат: ⚠️ HTTPS не отвечает",
    "commands.whois.source_just_now": "ℹ️ Данные получены: только что",
    "commands.whois.source_cached": "ℹ️ Данные из кэша, обновлены {ago}",
    "commands.whois.free": "🌐 {domain} — не зарегистрирован\n\nДомен свободен для регистрации.",
    # ------------------------------------------------------------------
    # /list — строка
    # ------------------------------------------------------------------
    "commands.list.row_known": "{emoji} {domain} — {days_until} ({date}){muted}",
    "commands.list.row_unknown": "{emoji} {domain} — нет данных{muted}",
    "commands.list.row_wishlist": "🎯 {domain} — жду освобождения",
    "commands.list.muted_suffix": " 🔕",
    "commands.list.unknown_value": "—",
    # Этап 9 — поиск/фильтры/wishlist
    "list.search.placeholder": "🔍 Поиск",
    "list.search.prompt": "Введите подстроку для поиска или /cancel",
    "list.search.current": "🔍 Поиск: <code>{query}</code>",
    "list.search.clear": "❌ Сбросить поиск",
    "list.search.empty": "По запросу <code>{query}</code> ничего не найдено.",
    "list.filter.critical": "🚨 С проблемами",
    "list.filter.expired": "💀 Истёкшие",
    "list.filter.wishlist": "🎯 Wishlist",
    # ------------------------------------------------------------------
    # /stats
    # ------------------------------------------------------------------
    "commands.stats.body": (
        "📊 Ваша статистика\n"
        "\n"
        "Всего доменов: {total}\n"
        "├ С данными: {with_data}\n"
        "└ Без данных: {without_data}\n"
        "\n"
        "Истекает:\n"
        "├ За 7 дней: {exp_7}\n"
        "├ За 30 дней: {exp_30}\n"
        "└ За 90 дней: {exp_90}\n"
        "\n"
        "🔕 Без уведомлений: {muted}\n"
        "📅 Добавлено за месяц: {added_month}"
    ),
    # ------------------------------------------------------------------
    # /settings
    # ------------------------------------------------------------------
    "commands.settings.menu": (
        "⚙️ Настройки\n"
        "\n"
        "🌍 Часовой пояс: {timezone}\n"
        "🕘 Время напоминаний: {hour:02d}:00\n"
        "🔔 Дни напоминаний: {notify_days}\n"
        "🌐 Язык: {language}"
    ),
    "commands.settings.choose_timezone": "Выберите часовой пояс или введите вручную:",
    "commands.settings.tz_prompt_manual": (
        "Введите имя часового пояса в формате IANA (например, Europe/Moscow). "
        "Или /cancel чтобы отменить."
    ),
    "commands.settings.tz_saved": "✅ Часовой пояс сохранён: {timezone}",
    "commands.settings.choose_time": "Выберите час, когда отправлять напоминания:",
    "commands.settings.time_saved": "✅ Время напоминаний: {hour:02d}:00",
    "commands.settings.choose_days": (
        "За сколько дней до истечения напомнить? Выберите пресет или введите свои:"
    ),
    "commands.settings.days_prompt_custom": (
        "Введите дни через пробел или запятую, например: 60 30 14 7 3 1\n"
        "Или /cancel чтобы отменить."
    ),
    "commands.settings.days_saved": "✅ Дни напоминаний: {notify_days}",
    "commands.settings.choose_language": "Выберите язык:",
    "commands.settings.language_saved": "✅ Язык сохранён: {language}",
    "commands.settings.lang_ru_name": "Русский",
    "commands.settings.lang_en_name": "English",
    # ------------------------------------------------------------------
    # /csv
    # ------------------------------------------------------------------
    "csv.empty": "У вас нет доменов для экспорта.",
    "csv.generating": "Готовлю файл с {count} доменами…",
    "csv.ready": "Файл готов: {count} доменов",
    # ------------------------------------------------------------------
    # /download
    # ------------------------------------------------------------------
    "download.intro": (
        "📥 Импорт доменов\n"
        "\n"
        "Пришлите файл TXT или CSV со списком доменов "
        "(по одному на строку или в первой колонке).\n"
        "\n"
        "Лимит: {limit} доменов за раз. Используйте /cancel чтобы отменить."
    ),
    "download.cancel": "Импорт отменён.",
    "download.timeout": "Время ожидания истекло, начните /download заново.",
    "download.no_file": "Пришлите файл или /cancel.",
    "download.too_large": "❌ Файл слишком большой, максимум {max_mb} МБ.",
    "download.parse_failed": "❌ Не удалось разобрать файл.",
    "download.rate_limit": "❌ Импорт можно делать не чаще {limit} раз в сутки.",
    "download.preview": (
        "📋 Найдено {total} доменов\n"
        "\n"
        "✅ Валидных и новых: {new}\n"
        "⚠️ Уже отслеживается: {already}\n"
        "❌ Невалидных: {invalid}"
    ),
    "download.preview_truncated": (
        "\n\n⚠️ Лимит {limit} доменов на один импорт. Остальное в файле проигнорировано."
    ),
    "download.confirm_button": "✅ Добавить {count}",
    "download.cancel_button": "❌ Отмена",
    "download.success": (
        "✅ Добавлено {count} доменов.\n"
        "Данные подгружаются в фоне, проверьте /list через несколько минут."
    ),
    "download.limit_exceeded": (
        "⚠️ Можно добавить только {fits} из {requested} — у вас лимит {limit} доменов.\n"
        "Удалите ненужные через /rmv или /list."
    ),
    "download.nothing_to_add": "Все домены из файла уже отслеживаются.",
    # ------------------------------------------------------------------
    # /admin
    # ------------------------------------------------------------------
    "admin.forbidden": "❌ Команда доступна только администраторам.",
    "admin.stats": (
        "📊 Статус системы\n"
        "\n"
        "👤 Пользователей: {users}\n"
        "🌐 Доменов в кэше: {cached_domains}\n"
        "📌 Подписок (user_domains): {tracked}\n"
        "⏳ Ожидают проверки: {due_checks}"
    ),
    "admin.alert_sent": "✅ Алерт отправлен.",
    "admin.alert_no_text": "Использование: /admin alert <текст>",
    "admin.alert_no_channel": "❌ ADMIN_CHANNEL_ID не настроен.",
    "admin.unknown": (
        "Доступные команды:\n"
        "/admin stats — текущая статистика\n"
        "/admin alert <текст> — тестовая отправка в канал"
    ),
    # ------------------------------------------------------------------
    # /download (старые ключи, использовались заглушкой)
    # ------------------------------------------------------------------
    "commands.download.prompt": (
        "📥 Импорт доменов\n"
        "\n"
        "Пришлите файл TXT или CSV со списком доменов "
        "(по одному на строку или в первой колонке).\n"
        "\n"
        "Лимит: {limit} доменов за раз."
    ),
    "commands.download.send_file_or_cancel": "Пришлите файл или /cancel",
    "commands.download.parse_failed": "❌ Не удалось разобрать файл.",
    "commands.download.preview": (
        "📋 Найдено {total} доменов\n"
        "\n"
        "✅ Валидных и новых: {new}\n"
        "⚠️ Уже отслеживается: {already}\n"
        "❌ Невалидных: {invalid}"
    ),
    "commands.download.done": (
        "✅ Добавлено {count} доменов.\n"
        "Данные подгружаются в фоне, проверьте /list через несколько минут."
    ),
    # ------------------------------------------------------------------
    # Уведомления (Этап 5)
    # ------------------------------------------------------------------
    "notifications.expiry.title": "⏰ Скоро истечёт регистрация",
    "notifications.expiry.body": (
        "⏰ <b>{domain}</b>\n"
        "\n"
        "📅 Истекает: {expires_at} (через {days_left})\n"
        "🏢 Регистратор: {registrar}\n"
        "\n"
        "Не забудьте продлить."
    ),
    "notifications.expiry.button_renewed": "✅ Уже продлил",
    "notifications.expiry.button_mute": "🔕 Не напоминать про этот домен",
    "notifications.change.registrar": (
        "🏢 <b>{domain}</b> — сменился регистратор\n\nБыло: {old}\nСтало: {new}"
    ),
    "notifications.change.ns": (
        "🌍 <b>{domain}</b> — сменились NS-серверы\n\nБыло: {old}\nСтало: {new}"
    ),
    "notifications.change.status": (
        "🔧 <b>{domain}</b> — изменились статусы\n\nБыло: {old}\nСтало: {new}"
    ),
    "notifications.change.expires_at": (
        "📅 <b>{domain}</b> — изменилась дата истечения\n\nБыло: {old}\nСтало: {new}"
    ),
    "notifications.change.registrant": (
        "👤 <b>{domain}</b> — изменился владелец\n\nБыло: {old}\nСтало: {new}"
    ),
    "notifications.change.privacy_revealed": (
        "👤 <b>{domain}</b> — владелец раскрыл данные\n\nТеперь: {new}"
    ),
    "notifications.change.privacy_hidden": (
        "👤 <b>{domain}</b> — владелец скрыл данные\n\nБыло: {old}"
    ),
    "notifications.change.button_open": "🌐 Открыть домен",
    "notifications.change.unknown": "—",
    "notifications.problem.title": "⚠️ Не удаётся проверить {domain}",
    "notifications.problem.body": (
        "⚠️ <b>{domain}</b>\n"
        "\n"
        "Не получается обновить WHOIS-данные.\n"
        "Последняя успешная проверка: {last_ok}\n"
        "Известная дата истечения: {expires_at}\n"
        "\n"
        "Попробуйте ещё раз вручную или проверьте, что домен ещё активен."
    ),
    "notifications.problem.button_retry": "🔄 Попробовать сейчас",
    "notifications.problem.button_mute": "🔕 Не уведомлять о проблемах",
    # ------------------------------------------------------------------
    # Уведомления — SSL (Этап 12, ADR 030)
    # ------------------------------------------------------------------
    "notifications.ssl_expiry.body": (
        "🔒 <b>{domain}</b> — скоро истечёт SSL-сертификат\n"
        "\n"
        "📅 Действителен до: {not_after} ({days_left})\n"
        "🏛️ Издатель: {issuer}\n"
        "\n"
        "Если у вас auto-renewal — проверьте, что он отрабатывает."
    ),
    "notifications.ssl_expiry.button_renewed": "✅ Обновил",
    "notifications.ssl_expiry.button_mute": "🔕 Не напоминать про этот сертификат",
    "notifications.ssl_change.issuer": (
        "🏛️ <b>{domain}</b> — сменился издатель SSL-сертификата\n\nТеперь: {issuer}"
    ),
    "notifications.ssl_change.not_after": (
        "🔒 <b>{domain}</b> — SSL-сертификат перевыпущен\n\nНовая дата истечения: {not_after}"
    ),
    "notifications.ssl_change.unreachable": (
        "⚠️ <b>{domain}</b> — HTTPS не отвечает\n\n"
        "Сайт перестал отдавать SSL-сертификат. Проверьте, что веб-сервер работает."
    ),
    "notifications.ssl_change.reachable": (
        "✅ <b>{domain}</b> — HTTPS снова работает"
    ),
    "notifications.ack.muted": "🔕 Уведомления для этого домена выключены",
    "notifications.ack.refresh_started": "🔄 Запустил повторную проверку",
    "notifications.ack.no_access": "❌ Этот домен не в вашем списке",
    "notifications.value.unknown": "—",
    "notifications.value.never": "никогда",
    "notifications.wishlist.available.title": "🎉 Домен <b>{domain}</b> освободился!",
    "notifications.wishlist.available.body": (
        "Можете зарегистрировать через любого регистратора.\n\n"
        "<i>Помните: автоматизированные drop-catchers могут оказаться быстрее "
        "ручного захвата популярных доменов.</i>"
    ),
    "notifications.wishlist.available.button_track": "📌 Начать отслеживать",
    "notifications.wishlist.available.button_dismiss": "OK",
    "notify.on": "🔔 Уведомления для {domain} включены",
    "notify.off": "🔕 Уведомления для {domain} выключены",
    # Этап 9 — /wishlist
    "commands.wishlist.empty": (
        "🎯 Wishlist пуст.\n\nДобавьте через /wishlist <code>example.com</code> "
        "или кнопку «Хочу когда освободится» в карточке /whois."
    ),
    "commands.wishlist.header": "🎯 Ваш wishlist ({total})\n\nСтраница {page}/{total_pages}",
    "commands.wishlist.added": (
        "🎯 <b>{domain}</b> добавлен в wishlist.\n"
        "Пришлю одно уведомление, когда домен освободится."
    ),
    "commands.wishlist.tracked_now": (
        "✅ <b>{domain}</b> теперь у вас в обычном /list. Удачной регистрации!"
    ),
    # ------------------------------------------------------------------
    # Inline-кнопки приветствия (callbacks из start_keyboard)
    # ------------------------------------------------------------------
    "start.check_prompt": (
        "🌐 Пришлите домен сообщением — покажу WHOIS.\n"
        "Или используйте команду: /whois example.com"
    ),
}
