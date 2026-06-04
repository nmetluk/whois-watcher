# 2026-06-05 — Prod: после редеплоя hotfix 77819f8 пропала кнопка запуска WebApp в /start

**Дата:** 2026-06-05 · **Контекст:** redeploy hotfix webapp-design (77819f8) на проде после v0.16.0 (fa3b996) · **Прод:** whois-watcher (wwb.all-2-all.com:8443) · **Исполнитель (локально):** nm (с docker)

> Реальный прод. Не писать секреты, реальные метрики пользователей и т.п.

## Задача / проблема
После успешного `git fetch/pull` + `bash scripts/deploy.sh` (fa3b996 → 77819f8) + `npm run build` webapp + рестарт бота кнопка «📱 Дашборд (WebApp)» в приветственном меню `/start` полностью исчезла (раньше присутствовала в локальной dev-сборке).

Пользователь: «теперь вообще пропала кнопка для webapp хотя раньше была».

Дополнительно не работали прямые команды `/webapp`, `/app`, `/dashboard`.

## Причина
Код интеграции кнопки WebApp (backend) никогда не попадал в main / GitHub:
- `webapp_url` computed property в Settings (из `webhook_base_url + /app/`)
- Расширение `start_keyboard(lang, *, webapp_url=None)` + условная кнопка с `WebAppInfo`
- Обновление `cmd_start` (принимает `settings: Settings`, передаёт url)
- Новый хэндлер `cmd_webapp` для прямых команд
- Локали `button.webapp` + `webapp.open_prompt` + упоминания в greeting/help
- Тесты

Этот код жил только в локальном uncommitted stash на прод-машине ("temp: local uncommitted changes (start.py webapp btn + ...) before redeploy of github bugfix 77819f8").

Hotfix 77819f8 (и предыдущие 0066–0084) были frontend + security + консолидация. В ww.txt после деплоя v0.16.0 прямо написано: «кнопка запуска в боте — в следующих итерациях».

77819f8 + наш предыдущий ручной ребилд фронта (vite base) не тронули backend-роутеры/клавиатуры.

## Выполнено (на прод-машине, до формального PR)
1. Перед редеплоем — обязательный ручной бэкап (manual-pre-77819f8/20260605-002206/, 59K dump, 165 TOC, верифицирован `pg_restore --list`).
2. `git stash` локальных изменений (чтобы `deploy.sh` прошёл — он требует чистого дерева).
3. После деплоя hotfix + ребилда фронта — диагностика: `git stash show`, сравнение текущих start.py / keyboards.py / settings.py с содержимым сташа.
4. Точечное восстановление **только** backend button (webapp/src/* не трогали — они были переписаны горячим фиксом дизайна):
   - `src/config/settings.py` (комментарий + `@computed_field webapp_url`)
   - `src/bot/keyboards.py` (WebAppInfo в импорте, сигнатура + реализация кнопки)
   - `src/bot/handlers/start.py` (Command + Settings, обновление cmd_start, новый cmd_webapp)
   - `src/locales/{ru,en}.py` (новые ключи + текст в greeting/help)
   - `tests/unit/test_keyboards.py` (тест без url + тест с url)
5. Для этого деплоймента также применён `base: '/app/'` в `webapp/vite.config.ts` (был в том же стэше; необходим для nginx `location /app/ { alias .../dist/ }` + same-origin /api/webapp/* + CSP).
6. `docker compose build bot` (py baked в образ) → `up -d bot`.
7. Верификация:
   - Внутри контейнера: `python -c 'from src.config.settings import get_settings; from src.bot.keyboards import start_keyboard; ...'` — с url: 4 кнопки, последняя "📱 Дашборд (WebApp)", `web_app` instance + правильный url; без url: ровно 3 кнопки.
   - `settings.webapp_url` → `https://wwb.all-2-all.com:8443/app/`
   - `curl http://127.0.0.1:8080/health` → ok
   - `docker compose ps` — bot healthy
   - `sudo /usr/local/bin/whois-watcher-monitor` → "All checks passed"
   - TG `getWebhookInfo` — pending=0, правильный url
   - Логи бота: чистый старт, "Webhook set", "Mounted /api/webapp"
8. Обновлён операторский `ww.txt` (шапка, новый раздел про redeploy + отдельная запись про восстановление кнопки).

## Изменённые файлы (кандидаты в upstream)
- `src/config/settings.py`
- `src/bot/keyboards.py`
- `src/bot/handlers/start.py`
- `src/locales/ru.py`
- `src/locales/en.py`
- `tests/unit/test_keyboards.py`

(Отдельно: `webapp/vite.config.ts` — деплоймент-конфиг этого прода; рекомендуется закоммитить base: '/app/' для соответствия документации в docs/deployment.md и nginx примерам.)

Полные диффы были в `git stash@{0}` (pre-redeploy) и отдельном post-stash для vite. Точный патч можно вытащить `git stash show -p stash@{N} -- <file>`.

## Проверки
- Логика кнопки: 4 vs 3 ряда, WebAppInfo присутствует, url заканчивается на /app/.
- Нет регрессий в существующих 3 кнопках (check / list / settings).
- Обратная совместимость: вызов `start_keyboard("ru")` без kwarg — работает (дефолт None).
- t() вызовы исправлены на позиционные (lang positional-only в `locales/__init__.py`).
- Прод-мониторинг и health — зелёные.
- Нет миграций, нет изменений БД.

## Что осталось / открытый вопрос
- Этот код до сих пор не в main. Нужно формализовать.
- В STATE.md на момент hotfix'а (и в задачах 0066–0084 / 0072 / 0074) явного таска на "кнопку запуска WebApp из /start + команды" не было (было только в ww.txt как "в следующих итерациях").
- Следующие итерации WebApp (v1.0 вне TG, публичный API и т.д.) — см. STATE "Следующий шаг".
- Хвосты из hotfix-сессии 2026-06-05_hotfix-webapp-design-fidelity.md остаются (demo-fallback в ListScreen, 5.3 МБ material-symbols, eslint webapp 43 ошибки).

## Рекомендация
**Да, нужно передать архитектору.**

Предлагаю:
1. Создать follow-up таск (или включить в существующий polish / v1 prep) через `python scripts/handoff.py new --title "WebApp launch button in /start + /webapp command" --milestone v0.16.1 или v1.0-prep`.
2. В задаче сослаться на эту сессию + ww.txt + hotfix-сессию.
3. Сделать нормальную ветку от свежего main (после 77819f8 + этого hotfix'а), применить патч, написать полноценный session-report по шаблону, прогнать pytest/mypy/ruff, открыть PR.
4. В STATE.md (в раздел "Последняя сессия" или "Открытые вопросы") добавить пометку про missing button integration.
5. Зафиксировать `base: '/app/'` в vite.config.ts (с комментарием про nginx).

Это мелкий, но видимый пользователю кусок v0.16 WebApp (ADR 043), который реально используется в проде (и упоминался в ww.txt как запланированный).

## Архитектурные решения / открытые вопросы (для STATE)
- Кнопка использует нативный `WebAppInfo` Telegram (не inline URL) — открывает внутри клиента, передаёт initData автоматически.
- webapp_url вычисляется централизованно в Settings — единая точка, как webhook_url.
- Локали обновлены в greeting/help, чтобы пользователи видели упоминание даже до тапа на кнопку.
- Прямые команды /webapp полезны для глубоких ссылок и BotFather menu button (альтернатива или дополнение).

## Ссылки
- Hotfix сессия: `docs/sessions/2026-06-05_hotfix-webapp-design-fidelity.md`
- Операторская заметка: `/home/nm/ww.txt` (обновлена)
- Предыдущий бэкап: `manual-pre-77819f8/20260605-002206/`
- Stash с оригинальным кодом: `stash@{0}` (и последующие) в локальной копии на прод-машине
- GitHub: https://github.com/nmetluk/whois-watcher (commit 77819f8)

## PR / коммиты
(пока локально на прод-машине; код в образе, но не закоммичен в git репо)

---

**Кратко для архитектора:** кнопка WebApp в /start (и команды) — missing piece v0.16. Была только локально. Восстановили на проде вручную после редеплоя hotfix'а. Нужно завести таск + PR, чтобы попало в репо официально. Diff небольшой и изолированный. Готов помочь с сессией/тестами.
