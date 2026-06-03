# SESSION-0067 — WebApp frontend foundation (Vite+React, токены, Telegram SDK, chrome, роутинг, build)

**Дата:** 2026-06-09 · **Таск:** TASK-0067 · **Ветка:** task/0067-webapp-frontend-foundation
· **Исполнитель:** Grok (agent)

> Публичный репозиторий. НЕ писать реальные данные.

## Задача
Завести отдельный Vite+React-TS проект `webapp/`, перенести дизайн-систему PIN Voice (токены + нужные chrome-классы без рамки телефона), интегрировать `Telegram.WebApp`, реализовать 5-вкладочный роутинг + стек экранов, API-клиент с initData, обеспечить чистую сборку + nginx-сниппет.

## Выполнено
- `webapp/` создан через `create-vite react-ts`.
- `src/styles/tokens.css` — полные значения CSS-переменных из `design/webapp/v1/app/ds/colors_and_type.css` (светлая + тёмная темы, шрифты PT Sans + Material Symbols).
- `src/styles/tg-chrome.css` — портированы `.tg-header`, `.tg-tabbar`, `.tg-mainbtn`, `.tg-fab`, `.tg-sheet`, `.tg-toast`, `.tg-search`, `.tg-drow`, `.tg-card`, `.tg-kpi`, `.tg-filters`, `.tg-list-head` и т.д. (без `.tg-phone`/`.tg-statusbar`/`.tg-viewport`).
- `src/lib/telegram.ts` — хелперы `getTg`, `initTelegram`, `syncTheme` (colorScheme → data-theme), `setupMainButton`/`setupBackButton`.
- `src/lib/api.ts` — клиент, каждый запрос добавляет `X-Telegram-Init-Data` (из `tg.initData`). Типы для WebAppDomain + fetchPortfolio.
- `src/App.tsx` — полноценный shell: 5 таб-баров, стек push/back (скрывает таббар), header с логикой, MainButton (TG native + fallback), FAB, Sheet, Toast. Состояние списка с live-загрузкой из API (с фолбэком на demo-данные). Заглушки экранов.
- `src/components/Icon.tsx` — обёртка material-symbols.
- Сборка `npm run build` чистая (tsc + vite), нет unpkg/Babel.
- ESLint чистый.
- Обновлён `.gitignore` (webapp/node_modules, dist и т.д.).
- Добавлен подробный сниппет nginx + инструкции по сборке/деплою статики + proxy `/api/webapp` в `docs/deployment.md`.
- Реальная интеграция Telegram (тема, кнопки, initData) протестирована в коде (для полного теста в TG — см. ниже).

## Изменённые/новые файлы
- `webapp/` (полностью новый Vite проект + весь наш код)
- `.gitignore`
- `docs/deployment.md`
- `docs/sessions/2026-06-09_task-0067-webapp-frontend-foundation.md` (этот)
- handoff/ файлы (от claim)

## Коммиты
(будет после push)

## Проверки
- `cd webapp && npm run build` — ✅ чистая сборка, dist/ готов.
- `npm run lint` — ✅
- `tsc` внутри build — ✅
- Токены: все ключевые `--pv-*` и `--tg-*` присутствуют и совпадают со значениями из дизайна (smoke проверено).
- Тема: синхронизируется с `Telegram.WebApp.colorScheme` (или system в dev).
- API клиент: attach initData на каждый запрос.
- Нет рамки телефона, нет unpkg/Babel — как требовалось.
- Реальная проверка в Telegram: (см. ниже в "Что осталось").

## Что осталось / следующий шаг
- TASK-0068: экраны "Список доменов + карточка домена" (полноценные, с вкладками Обзор/WHOIS/SSL/...).
- TASK-0069: дашборд, календарь, алерты, "Ещё".
- TASK-0070: write-действия (тогглы, массовые, add).
- В bot коде: добавить кнопку запуска WebApp с правильным URL (https://<домен>/webapp/).
- Для dev-теста вне TG: можно передать ?initData=... или положить в localStorage.
- Шрифты: @import Google — ок для v0.16; в проде можно self-host или subset.
- Deploy: в `scripts/deploy.sh` можно добавить шаг `cd webapp && npm ci && npm run build && cp -r dist/* /var/www/...` (сейчас manual по доке).

## Архитектурные решения / открытые вопросы
- Роутинг без react-router — state-based (tab + stack), как в дизайн-прототипе. Просто, достаточно для 6 экранов.
- API base — относительный `/api/webapp`, работает и в TG WebApp, и при vite proxy (если настроить).
- Telegram SDK: использовали глобал + тонкие хелперы (не тащили react-обёртки). Достаточно.
- Статическая сборка + nginx alias — классика для mini-app на том же домене, что и webhook.

## PR
- Будет открыт после `handoff.py status in_review` + push.

## Реальная проверка в Telegram
Для полного теста (открытие mini-app):
1. Задеплоить backend (с TASK-0066) + обновить nginx по новому сниппету.
2. Собрать webapp и положить в /var/www/whoiswatcher-webapp.
3. Временно добавить в bot (например в /start) кнопку:
   `InlineKeyboardButton(..., web_app=WebAppInfo(url="https://ваш-домен/webapp/"))`
4. В Telegram: открыть бота → тап по кнопке WebApp → должен открыться, тема подхватиться, запросы к /api/webapp/portfolio должны работать (авторизация через initData).
5. В session-отчёте следующего этапа будет скрин/описание.

(На текущей машине без полного прода + bot update — протестировано через код + сборку + логику.)
