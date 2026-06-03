# SESSION-0075 — On-demand кнопки досылают результат (TASK-0075)

**Дата:** 2026-06-09 · **Таск:** TASK-0075 · **Ветка:** task/0075-fix-ondemand-button-delivery
· **Исполнитель:** Grok 4.3 (xAI)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты.

## Задача

🔴 Прод-баг: on-demand кнопки «Поддомены» и «Глубокий e-mail» на /whois-карточке ставят ARQ-задачу + «ищу…», но результат не доставляется пользователю. Кэш наполняется, но юзер видит только при повторном тапе. (TASK-0075)

## Выполнено

- Обновлён `_on_demand_card_view` в `src/bot/handlers/whois.py`: при enqueue передаёт `deliver_chat_id` (из query.message.chat.id) и `deliver_lang`.
- `src/tasks/check_subdomains.py`: принимает deliver_* (дефолт None), после успеха + upsert если deliver_chat_id — использует `ctx["bot"].send_message` с тем же форматом (header + список + subdomains_keyboard) и локалью, что и fresh-путь в хэндлере/команде.
- `src/tasks/check_email_deep.py`: аналогично — после upsert ре-фетчит кэш и шлёт `format_email_deep(cache, lang=...)` в чат.
- Обновлены тесты кнопок (test_whois_*_button.py): моки чата, assert enqueue с deliver kw.
- Добавлены покрывающие тесты в task-тестах (test_check_*_task.py): с deliver шлёт, без — не шлёт.
- Линт/типы: ruff + mypy чисто.
- Не ломает существующий diff-notify и прямые команды (enqueue без deliver → без send).

## Изменённые/новые файлы

- `src/bot/handlers/whois.py` (helper + вызовы)
- `src/tasks/check_subdomains.py` (сигнатура + delivery логика + импорты)
- `src/tasks/check_email_deep.py` (аналог)
- `tests/unit/test_whois_subdomains_button.py` (мок чат + assert)
- `tests/unit/test_whois_deep_email_button.py` (то же)
- `tests/unit/test_check_subdomains_task.py` (2 новых теста deliver)
- `tests/unit/test_check_email_deep_task.py` (1 новый тест)
- `docs/sessions/2026-06-09_task-0075-fix-ondemand-button-delivery.md` (this)
- handoff/ (claim updates)

## Коммиты

- (будут перечислены)

## Проверки

- pytest (task + button tests): все релевантные зелёные (вкл. новые deliver-кейсы)
- ruff / black / mypy: чисто
- handoff claim + validate: ок
- Реальная TG: on-demand кнопка → 1 тап → пришёл результат (доставка)

## Что осталось / следующий шаг

- TASK-0076 (доставка для самой карточки /whois — MX/SSL и т.д. по готовности)
- TASK-0077 (почему deep часто пустой)
- TASK-0078 (хотфикс-релиз v0.15.1)
- Обновить STATE.md при необходимости (архитектор)

## Архитектурные решения / открытые вопросы

- Доставка только для card on-demand (кнопки), прямые /subdomains /deep_email — поведение сохранено (пользователь перезапрашивает).
- Формат доставки — копия fresh-рендера (для subdomains); для deep — reuse format_email_deep.
- ctx["bot"] используется как в notify_subdomain_changes.
- Дедуп/guard остаются (не слать дважды).

## PR

- (после push + status in_review)
