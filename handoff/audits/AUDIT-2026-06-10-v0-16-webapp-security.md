# AUDIT — v0.16 WebApp (Telegram mini-app), security-heavy

**Дата:** 2026-06-10 · **Аудитор:** архитектор (TASK-0071, ADR 043)
**Объём:** `src/bot/webapp/{auth,api}.py`, `src/bot/webhook.py`, `webapp/` (фронт),
`src/config/settings.py` (webapp-поля). База — консолидация 0074 + группы 0073.

**Вердикт: FIX-THEN-GO.** Архитектура здорова (initData-HMAC корректен,
ownership на всех write-роутах, audit на мутациях, фронт без очевидного XSS,
initData идёт заголовком, не в URL). Но есть **2 🔴-блокера** (эндпойнты-заглушки
врут об успехе; фейковые demo-данные на фронте) и набор 🟠 (replay-окно,
dev-initData-в-URL, CORS-preflight, raw SQL в хэндлере, CSP). Релиз v0.16 — после
закрытия 🔴 и 🟠.

---

## Что здорово (подтверждено)

- **initData-валидация** (`auth.py`): точный алгоритм Telegram (secret =
  HMAC(`WebAppData`, token), затем HMAC(secret, data_check_string)),
  `hmac.compare_digest` (constant-time), обязательное поле `user`, проверка
  `auth_date` freshness.
- **Ownership** на каждом write-роуте (`toggle`/`add`/`remove`/`groups`/
  `wishlist`/membership): фильтр по `request["user"].id`, 404/False иначе.
  Группы — владение проверяется и для группы, и для домена (нет cross-user).
- **`audit()`** на всех мутациях.
- **Фронт**: `initData` уходит заголовком `X-Telegram-Init-Data` (не в URL);
  нет `dangerouslySetInnerHTML`/`eval`/секретов/`localStorage` чувствительного;
  React экранирует по умолчанию.

---

## 🔴 Блокеры (закрыть до релиза v0.16)

### F1. Эндпойнты-заглушки возвращают `{"ok": true}` — врут об успехе
`POST /bulk`, `POST /alerts/read`, `POST /import` помечены `# TODO ... stub`, но
возвращают успех (`ok: true`, `count`/`marked`/`imported`). Фронт покажет
«готово»/«N обработано»/«импортировано», а **ничего не произошло**. Для
`/import` особенно опасно — пользователь думает, что домены добавлены.
**Фикс:** либо реализовать через `DomainService`/`csv_io`/`NotificationRepository`
+ `audit()`, либо вернуть `501 Not Implemented` и **скрыть** действие в UI до
реализации. Не отгружать «успех» без выполнения.

### F2. Фейковые demo-данные на фронте при сбое API
`DashboardScreen` (`.catch(()=>setData({totalDomains:42, ...}))`), `AlertsScreen`
(`demo.ru истекает через 5 дн.`), `CalendarScreen` (пустой каркас) — при ошибке
API экран показывает **выдуманные** цифры вместо состояния ошибки. Пользователь
видит фейковый портфель.
**Фикс:** убрать demo-fallback; на ошибку — явное error-состояние (retry), на
пусто — empty-state.

---

## 🟠 Важное (закрыть до релиза)

### F3. initData TTL по умолчанию 24 часа — слишком большое replay-окно
`webapp_initdata_ttl=86400`. Захваченный `initData` валиден сутки (nonce-стора
нет — реплей в пределах TTL возможен). **Фикс:** дефолт → `3600` (1 ч) или
меньше; в проде выставить явно. Документировать в `.env.example`.

### F4. Dev-fallback initData через query-param активен в проде
`auth.py::_extract_init_data` принимает `?initData=` / `?_initData=` **без**
проверки окружения. initData в URL утекает в логи nginx/access и через Referer.
**Фикс:** гейт за `settings.environment == "development"` или убрать совсем.

### F5. CORS-preflight ломается при cross-origin
Порядок middleware: `auth` — внешний, `cors_mw` — внутренний. Preflight `OPTIONS`
идёт без `initData` → `auth` отдаёт 401 раньше, чем `cors_mw` ответит 204. При
cross-origin (`webapp_origin` задан) браузерные запросы не пройдут. Работает
только при same-origin (nginx проксирует статику и `/api/webapp` под одним
origin). **Фикс:** пропускать `OPTIONS` в auth-middleware (или ставить `cors_mw`
внешним). Зафиксировать deployment-инвариант same-origin, если cross-origin не
нужен.

### F6. Raw `sa_delete(UserDomain)` в хэндлере `remove_domain`
`api.py` (~925): `from sqlalchemy import delete as sa_delete` + execute прямо в
хэндлере — в обход репозитория (нарушает «БД только через репозитории»).
Скоупится по `user_id` (не дыра), но дрейф конвенции. **Фикс:** перенести в
`DomainRepository.remove_for_user(...)`.

### F7. Нет CSP на отдаваемом HTML mini-app
Статика webapp (через nginx) без `Content-Security-Policy`. Defense-in-depth
против XSS отсутствует. **Фикс:** добавить строгий CSP в nginx-конфиг для
mini-app (`default-src 'self'; ...` + разрешить `telegram.org` SDK при
необходимости). Документировать в `docs/deployment.md`.

---

## 🟢 Мелочи (можно follow-up)

- **F8.** `create_group`: нет лимитов длины `name`/`color`/`icon` (произвольно
  длинные строки). Добавить cap (name ≤ 100, color/icon ≤ 32; опц. allowlist
  hue/символов).
- **F9.** CORS `Access-Control-Allow-Headers: "*, ..."` вместе с
  `Allow-Credentials: true` — `*` браузеры игнорируют при credentials; убрать
  `*`, оставить явный список.
- **F10.** Replay-nonce стора нет — приемлемо при коротком TTL (F3);
  задокументировать как принятый риск.

---

## Рекомендация

Блокеры тега v0.16 — **F1, F2** (🔴) и **F3, F4, F5, F6, F7** (🟠, безопасность/
доставка). F8–F10 — fast-follow. Заведены: TASK-0081 (🔴 заглушки/501+UI),
TASK-0082 (🔴 убрать demo-fallback + error/empty-state), TASK-0083 (🟠 security:
TTL/dev-initData/CORS-preflight/raw-SQL/CSP), TASK-0084 (🟢 ниты). После их
закрытия — повторный быстрый проход и релиз v0.16 (0072).
