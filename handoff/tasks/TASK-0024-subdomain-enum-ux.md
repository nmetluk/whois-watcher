---
id: TASK-0024
title: UX — команда /subdomains + opt-in отслеживание + локали (ADR 037)
status: open
milestone: v0.11.0
adr: 037
area: code
depends_on: [TASK-0023]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-30
---

# TASK-0024 — UX subdomain enumeration (ADR 037)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Команда `/subdomains <domain>`: показать найденные поддомены (read-only) и дать
**opt-in** — взять выбранные на отслеживание через существующий `/add`-путь.

## Контекст

ADR 037. crt.sh-запрос медленный → команда отвечает «ищу…» и ставит ARQ-задачу
`check_subdomains` (TASK-0023); по готовности — список с кнопками.

## Изменения по файлам

- `src/bot/handlers/` — новый хэндлер `/subdomains` (тонкий): валидация домена
  (ADR 035, guard на публичный суффикс/мусор), запрос по registrable, ответ
  «ищу…», enqueue `check_subdomains`; рендер кэш-результата если свежий (TTL).
- Рендер списка + inline-кнопки «отслеживать» (по поддомену или пачкой) —
  при нажатии идём в существующий `/add`-путь (`DomainService.add_for_user` /
  promote, ADR 034/035). **Соблюсти лимит 50k** (ADR 011) — при превышении
  понятная ошибка, без частичного мусора.
- `src/bot/keyboards.py` / `states.py` — клавиатура выбора/подтверждения.
- `src/locales/ru.py`, `en.py` — **все** новые строки (заголовок списка,
  «ищу…», «ничего не найдено», «crt.sh временно недоступен», кнопки). Инвариант
  `test_all_ru_keys_present_in_en`.
- Зарегистрировать команду в роутере и (опц.) в меню BotFather-доках.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `/subdomains` не падает на мусорном/IDN-вводе и на пустой выдаче.
- crt.sh недоступен → понятное сообщение, не ошибка.
- Opt-in идёт через `/add`-путь; лимит 50k соблюдён; авто-добавления нет.
- `test_all_ru_keys_present_in_en` зелёный.
- Моки хэндлеров/сервисов — со `spec`/`autospec` (anti-drift, CLAUDE.md);
  покрыть путь кнопки opt-in → `/add` (callback), чтобы дрейф сигнатур падал.

## Требования к тестам

- `tests/unit/test_subdomains_handler.py` (+ рендер списка, opt-in callback,
  degradation). Real-world проверка в Telegram желательна.

## Definition of Done

- [ ] `/subdomains` работает: список + opt-in через `/add`; degradation; локали ru/en
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный
- [ ] После 0022–0024 — релиз v0.11.0

## Ссылки

- ADR 037; ADR 035 (registrable/guard), ADR 034 (promote), ADR 011 (лимит 50k).

---

## Ревью v1 — требуемые правки (2026-05-30)

PR #17 вернулся на доработку. **Корень:** `SubdomainAction` пакует в
callback_data полный FQDN поддомена + `registrable` → превышает лимит Telegram
**64 байта** (проверено на aiogram 3.28.2: `.pack()` бросает
`ValueError: Resulted callback data is too long!`). crt.sh регулярно отдаёт
длинные FQDN → `subdomains_keyboard()` упадёт и `/subdomains` крашится. Плюс
кнопки все подписаны одинаково «📌 Отслеживать» (имени поддомена не видно), а
сам `header` список не рендерит.

Обязательно до мержа:

1. **`src/bot/keyboards.py`** — в `SubdomainAction` заменить `subdomain: str`
   на `idx: int = -1` (индекс в `cached.subdomains`). В `subdomains_keyboard`
   паковать `idx`, кнопки подписывать именем: `text=f"📌 {from_punycode(sub)}"`
   (добавить импорт `from_punycode`), убрать `resize_keyboard=True` (это
   параметр ReplyKeyboard, не Inline), поправить комментарий «~100 байт» → 64.
   Раскладка `builder.adjust(*([1]*len(shown) + [2]))`.

2. **`src/bot/handlers/subdomains.py::cb_subdomains_track`** — доставать
   поддомен из кэша по `callback_data.idx` (guard out-of-range → `no_cache`).
   Считать успехом статусы **`added / added_pending / promoted`** (сейчас
   только `added`; для свежего поддомена типичный ответ — `added_pending` →
   падает в `else` → показывает «❌ Некорректный домен» при фактическом успехе).
   Реальные статусы `AddDomainResult`:
   `invalid_domain / limit_reached / promoted / already_tracked / added / added_pending`.

3. **`cb_subdomains_track_all`** — добавить `promoted` в success-ветку
   (`added += 1`); сейчас `promoted` уходит в `error_count`.

4. **`cmd_subdomains`** — убрать неиспользуемый параметр `redis: Redis[str]`
   и импорт `from redis.asyncio import Redis`.

5. **Тесты** (`tests/unit/test_subdomains_handler.py`, моки со `spec`/`autospec`):
   - успешный track при `add_for_user → added_pending` (НЕ показывает invalid_domain);
   - то же для `promoted`;
   - `subdomains_keyboard` на длинном FQDN не бросает и каждый track-callback
     `len(.encode()) <= 64` (прямой guard от регрессии длины);
   - track_all считает `promoted` как `added`.

Обязательно: правки 1–2 + тесты на них. Правка 3 и тест track_all — желательно
в том же PR. Дорабатывать в той же ветке `task/0024-subdomain-enum-ux`.

---

## Ревью v2 — фиксы НЕ сделаны, повтор с дословным diff (2026-05-30)

Коммит `a85c9eb` («фиксы 1 и 2») по факту изменил **только текст кнопок и
текст сообщения** (имена поддоменов). Это полезно — **оставить**. Но оба
блокера остались НЕТРОНУТЫМИ:

- `SubdomainAction.subdomain` на месте → callback_data всё ещё пакует полный
  FQDN → лимит 64 байта превышается → `/subdomains` крашится на длинных FQDN.
- `cb_subdomains_track` всё ещё `if status == "added" … else` → `added_pending`
  (типичный случай) показывает «❌ Некорректный домен» при успехе.

⚠️ Текст кнопки ≠ callback_data. Менять надо **`callback_data`** и **логику
статусов**, не подписи. Ниже — дословно.

### Правка 1а — `src/bot/keyboards.py`, класс `SubdomainAction`

```diff
 class SubdomainAction(CallbackData, prefix="sub"):
     action: str  # "track" | "track_all" | "refresh"
     registrable: str  # registrable-домен
-    subdomain: str = ""  # конкретный поддомен (для action="track")
+    idx: int = -1  # индекс поддомена в cached.subdomains (для action="track")
```

### Правка 1б — `src/bot/keyboards.py`, `subdomains_keyboard`

```diff
-    for subdomain in subdomains[:_MAX_SUBDOMAIN_BUTTONS]:
-        display = from_punycode(subdomain)
+    for idx, subdomain in enumerate(subdomains[:_MAX_SUBDOMAIN_BUTTONS]):
+        display = from_punycode(subdomain)
         builder.button(
             text=f"📌 {display}",
             callback_data=SubdomainAction(
                 action="track",
                 registrable=registrable,
-                subdomain=subdomain,
+                idx=idx,
             ).pack(),
         )
```
И в конце функции убрать `resize_keyboard=True` (это параметр ReplyKeyboard,
для Inline бессмысленен): `return builder.as_markup()`.

### Правка 2 — `src/bot/handlers/subdomains.py`, `cb_subdomains_track`

```diff
-    subdomain = callback_data.subdomain
-    if not subdomain:
-        await callback.answer(t("errors.invalid_domain", lang), show_alert=True)
-        return
+    registrable = callback_data.registrable
+    idx = callback_data.idx
+    async with get_session() as session:
+        cache_repo = SubdomainEnumCacheRepository(session)
+        cached = await cache_repo.get(registrable)
+    if not cached or not cached.subdomains or idx < 0 or idx >= len(cached.subdomains):
+        await callback.answer(t("commands.subdomains.no_cache", lang), show_alert=True)
+        return
+    subdomain = cached.subdomains[idx]
```
И в блоке статусов:
```diff
-    if result.status == "added":
+    if result.status in ("added", "added_pending", "promoted"):
         await callback.answer(
             t("commands.add.success_no_data", lang, domain=display), show_alert=True
         )
```
(ветки `already_tracked` / `limit_reached` / `else` — без изменений.)

### Правка 3 — `cb_subdomains_track_all` (тот же файл)

```diff
-            if result.status in ("added", "added_pending"):
+            if result.status in ("added", "added_pending", "promoted"):
                 added += 1
```

### Правка 4 — `cmd_subdomains` (тот же файл)

Убрать из сигнатуры неиспользуемый `redis: Redis[str]` и импорт
`from redis.asyncio import Redis`.

### Тесты (обязательно — иначе фиксы не доказаны)

В `tests/unit/test_subdomains_handler.py` (моки со `spec`/`autospec`):

1. **callback ≤ 64 байта** на длинном FQDN — прямой guard от регрессии:
   ```python
   kb = subdomains_keyboard(
       "example.co.uk",
       ["autodiscover.internal.staging.example.co.uk"],
       lang="ru",
   )
   for row in kb.inline_keyboard:
       for btn in row:
           if btn.callback_data and btn.callback_data.startswith("sub:track"):
               assert len(btn.callback_data.encode()) <= 64
   ```
2. **success-track при `added_pending`** — `cache.get` → запись с
   `subdomains=["www.example.com"]`; `add_for_user` (autospec) →
   `AddDomainResult(status="added_pending", normalized_domain="www.example.com")`;
   `callback_data=SubdomainAction(action="track", registrable="example.com", idx=0)`;
   assert `callback.answer` вызван с `success_no_data`, **не** с `invalid_domain`.
3. то же для `status="promoted"`.

Косметические тесты из v1 (`test_button_contains_subdomain_name`,
`test_message_contains_subdomain_list`) — оставить.

Готово к мержу = правки 1–2 + тесты 1–3 фактически в коде (проверю diff,
а не текст кнопок).
