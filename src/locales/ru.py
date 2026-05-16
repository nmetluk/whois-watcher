"""Русская локаль. Ключи — `dot.case.path`.

Все пользовательские тексты бота — отсюда. Не хардкодить строки в хэндлерах.
Тон умеренный, эмодзи только как индикаторы статусов (ADR 021).
"""

from __future__ import annotations

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
    "commands.whois.section_status": "🔧 Статусы:",
    "commands.whois.section_ns": "🌍 NS-серверы:",
    "commands.whois.source_just_now": "ℹ️ Данные получены: только что",
    "commands.whois.source_cached": "ℹ️ Данные из кэша, обновлены {ago}",
    "commands.whois.free": "🌐 {domain} — не зарегистрирован\n\nДомен свободен для регистрации.",
    # ------------------------------------------------------------------
    # /list — строка
    # ------------------------------------------------------------------
    "commands.list.row_known": "{emoji} {domain} — {days_until} ({date}){muted}",
    "commands.list.row_unknown": "{emoji} {domain} — нет данных{muted}",
    "commands.list.muted_suffix": " 🔕",
    "commands.list.unknown_value": "—",
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
    "notifications.ack.muted": "🔕 Уведомления для этого домена выключены",
    "notifications.ack.refresh_started": "🔄 Запустил повторную проверку",
    "notifications.ack.no_access": "❌ Этот домен не в вашем списке",
    "notifications.value.unknown": "—",
    "notifications.value.never": "никогда",
    "notify.on": "🔔 Уведомления для {domain} включены",
    "notify.off": "🔕 Уведомления для {domain} выключены",
    # ------------------------------------------------------------------
    # Inline-кнопки приветствия (callbacks из start_keyboard)
    # ------------------------------------------------------------------
    "start.check_prompt": (
        "🌐 Пришлите домен сообщением — покажу WHOIS.\n"
        "Или используйте команду: /whois example.com"
    ),
}
