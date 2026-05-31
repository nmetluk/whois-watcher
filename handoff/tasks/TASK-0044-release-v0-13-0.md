---
id: TASK-0044
title: Релиз v0.13.0 — deep email + on-demand views (ADR 040)
status: open
milestone: v0.13.0
adr: 040
area: docs
depends_on: [TASK-0043]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-31
---

# TASK-0044 — Релиз v0.13.0 (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Гейт:** не стартовать, пока не закрыт аудит TASK-0043 (вердикт go) и не
> смержены TASK-0038…0042.

## Цель

Выпустить минорный релиз **v0.13.0** — углублённый почтовый слой + on-demand
deep-views (ADR 040).

## Предусловия

- TASK-0038…0042 смержены в main; TASK-0043 (аудит) — вердикт go; CI зелёный
  (полный `pytest`, `ruff`/`black --check`/`mypy src`, migration round-trip).
- Alembic-head единственный (новая миграция `email_deep_cache` из TASK-0039).

## Изменения по файлам

- `pyproject.toml` — bump `version` `0.12.0` → `0.13.0`.
- `CHANGELOG.md` — секция `## [0.13.0] — ...`: deep email (SPF include-резолвинг,
  MTA-STS, TLS-RPT, DANE/TLSA, BIMI), инлайн MX+статус в `/whois`, кнопки
  «Глубокий e-mail» и «Поддомены» (on-demand), фикс свежести карточки.
- `STATE.md` — отметить релиз.

## Миграции БД

Новых в релизном таске нет — `email_deep_cache` уже в main (TASK-0039).

## Definition of Done

- [ ] Предусловия выполнены (0038–0042 в main, аудит go, CI зелёный)
- [ ] `pyproject` bump 0.12.0 → 0.13.0; секция `[0.13.0]` в CHANGELOG
- [ ] Аннотированный тег `v0.13.0` на актуальном main
- [ ] Деплой (`bash scripts/deploy.sh`)
- [ ] `handoff.py validate`; STATE.md обновлён; PR + зелёный CI

## Ссылки

- ADR: `docs/decisions.md` (ADR 040)
- Аудит: TASK-0043; образец релизного таска: TASK-0036
