---
id: TASK-0005
title: UX поддоменов — /whois, /add, /list, локали
status: open
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0004]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0005 — UX поддоменов: /whois, /add, /list, локали (подэтап 2d)

> Самодостаточно. Процесс — `handoff/README.md`. Дизайн — ADR 035.
> Финальный подэтап v0.9.0: пользовательский слой поверх 2a–2c.

## Цель

Пользователь видит, что добавил поддомен: WHOIS показан у родителя с
баннером, DNS/SSL — у поддомена; в `/list` поддомен помечен значком.

## Контекст / корень проблемы

Логика (2a–2c) готова, но без UX пользователь не понимает поведения и
не может включить слежение DNS/SSL поддомена.

## Изменения по файлам

- `src/bot/handlers/whois.py` — при вводе поддомена:
  баннер «🔎 a.pinbetting.ru — поддомен pinbetting.ru. WHOIS показан для
  родителя.»; карточка WHOIS родителя; DNS/SSL-блоки для **поддомена**;
  inline-кнопки «Следить за DNS», «Следить за SSL» поддомена.
- `src/bot/handlers/add_remove.py` (или сервис) — `/add a.pinbetting.ru`
  создаёт строку: `domain=a.pinbetting.ru`, `registrable_domain` и
  `is_subdomain` через `utils.domains`, `track_dns=true`,
  `track_ssl=true`; `notify_expiry` работает от родителя.
- `src/services/formatters*.py` — пометка поддомена значком `↳` и показ
  родительского expiry в строке `/list`.
- ввод чистого публичного суффикса (`co.uk`) → `errors.public_suffix_not_domain`.
- `src/locales/ru.py`, `src/locales/en.py` — ключи:
  `whois.subdomain_banner`, `commands.add.subdomain_added`,
  `errors.public_suffix_not_domain`, подпись `↳` в списке.
- `CHANGELOG.md` (Unreleased→0.9.0), `pyproject.toml` → 0.9.0, `uv.lock`.

## Миграции БД

Не требуется (схема уже в TASK-0003).

## Инварианты (защитить тестами)

- `/whois` поддомена → баннер + карточка родителя; «свободен» не
  показывается, если родитель занят.
- `/add` поддомена → корректные `registrable_domain`/`is_subdomain`,
  `track_dns`/`track_ssl` = true.
- `/list` помечает поддомен `↳` и показывает родительский expiry.
- `co.uk` → `errors.public_suffix_not_domain`.
- Все новые тексты — через локали, не хардкод (ru + en).

## Требования к тестам

- Хэндлер `/whois` поддомена (баннер, источник карточки).
- `/add` поддомена (поля строки, дефолты toggle'ов).
- Форматтер `/list` (значок `↳`, родительский expiry).
- Локали: оба языка содержат новые ключи.

## Definition of Done

- [ ] UX `/whois` + `/add` + `/list` + локали реализованы
- [ ] Тесты по инвариантам зелёные; `pytest` полный прогон
- [ ] `ruff`/`black`/`mypy` чисто
- [ ] Бамп `pyproject.toml`→0.9.0, `CHANGELOG.md`, `uv.lock`
- [ ] Real-world Telegram-тест поддомена (DNS/SSL toggle'ы работают)
- [ ] Per-session отчёт в `docs/sessions/`, вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR 035, `PLAN_subdomains_wishlist.md` (Этап 2, 2d)
- Зависит от: TASK-0004
