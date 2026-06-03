---
id: TASK-0075
title: 🔴 Фикс — on-demand кнопки не досылают результат (поддомены, глубокий e-mail)
status: open
milestone: v0.15.1
adr: 040
area: code
depends_on: []
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-09
---

# TASK-0075 — On-demand кнопки досылают результат (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🔴 Прод-баг (фидбек пользователей #1 «Поддомены», #2 «Глубокий e-mail»).

## Корень проблемы (подтверждён по коду)

`_on_demand_card_view` (`src/bot/handlers/whois.py`): если кэш не свежий —
`arq_redis.enqueue_job(...)` + reply «⏳ ищу…». Но **задача не доставляет
результат пользователю**:
- `check_subdomains` шлёт `notify_subdomain_changes` **только при diff'е**
  (изменениях), а не «вот список тому, кто нажал»;
- `check_email_deep` пользователю **не шлёт ничего**.
Кэш наполняется, но юзер видит результат лишь при **повторном** нажатии (тогда
кэш свежий → рендер). Отсюда «пишет ищу, но не приходит; со второго раза ок».

## Цель

По завершении on-demand проверки (запущенной кнопкой) **доставить результат в
чат пользователю** — без повторного нажатия.

## Изменения по файлам

- Передавать в задачу контекст доставки: `enqueue_job("check_subdomains",
  registrable, deliver_chat_id=<chat>, deliver_lang=<lang>)` и аналогично
  `check_email_deep`.
- `src/tasks/check_subdomains.py`: при успешном upsert, если задан
  `deliver_chat_id` — отправить форматированный список поддоменов в этот чат
  (через `ctx["bot"]`, тем же форматтером/клавиатурой, что и fresh-путь хэндлера).
- `src/tasks/check_email_deep.py`: при успехе, если задан `deliver_chat_id` —
  отправить `format_email_deep(cache)` в чат.
- Хэндлер кнопок: передавать `deliver_chat_id`/`lang` при enqueue; reply «ищу…»
  оставить. Дедуп: redis-guard уже есть; не слать дважды.
- Вынести общий «доставочный» помощник, если уместно.

## Инварианты (защитить тестами)

- Кнопка на не-свежем кэше → enqueue с `deliver_chat_id`; по завершении задачи
  `bot.send_message` в этот чат с результатом (тест: задача с `deliver_chat_id`
  шлёт; без него — не шлёт, как раньше).
- Свежий кэш → как сейчас (мгновенный рендер, без enqueue).
- Не ломать существующий `notify_subdomain_changes` (diff-уведомления).

## Definition of Done

- [ ] Поддомены и глубокий e-mail досылают результат по готовности (без 2-го тапа)
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Реальная проверка в Telegram (нажал один раз → пришёл список/разбор)
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 040; `src/bot/handlers/whois.py` (`_on_demand_card_view`),
  `src/tasks/{check_subdomains,check_email_deep}.py`.
- Связанные: TASK-0076 (та же доставка для карточки), 0077 (deep пустой).
