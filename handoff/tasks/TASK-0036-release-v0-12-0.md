---
id: TASK-0036
title: Релиз v0.12.0 — мониторинг поддоменов (ADR 037+038)
status: in_review
milestone: v0.12.0
adr: 038
area: docs
depends_on: [TASK-0033, TASK-0034, TASK-0035, TASK-0037]
branch: task/0036-release-v0-12-0
owner: ""
session: docs/sessions/2026-05-31_task-0036-release-v0-12-0.md
pr: #27
created: 2026-05-31
---

# TASK-0036 — Релиз v0.12.0

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Гейт:** не стартовать, пока не смержены **все** фиксы аудита:
> ✅ 🟠 TASK-0033, ✅ 🟠 TASK-0034 (тест-гэпы), 🟡 **TASK-0035**
> (N+1 + дедуп toggle'ов), 🟢 **TASK-0037** (html.escape + кап интервала).
> Решение владельца 2026-05-31: влить все фиксы в v0.12.0 (не выносить в
> v0.12.1). См. `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`.

## Цель

Выпустить минорный релиз **v0.12.0** — periodic subdomain monitoring
(ADR 037 enumeration + ADR 038 мониторинг/алерты), стек TASK-0027…0029.
Код уже на main (`3fa2d12` и поздн.), аудит пройден; релиз — после закрытия
блокеров.

## Контекст / корень проблемы

`pyproject.toml` на main = `0.11.1` (легитимно отстаёт от фич v0.12). Секция
`[Unreleased]` в `CHANGELOG.md` пуста — изменения v0.12 в журнал ещё не
внесены. Аудит TASK-0030 дал вердикт fix-then-go: тег ставим **после** мержа
TASK-0033 (тесты fan-out) и TASK-0034 (тесты success→enqueue).

## Предусловия (проверить перед тегом)

- Смержены в main и CI зелёный (полный `pytest`, `ruff`/`black --check`/
  `mypy src`, migration round-trip на Postgres): TASK-0033, TASK-0034
  (✅ done), TASK-0035, TASK-0037.
- Единственный alembic-head = `20260530_subdomain_monitor` (подтверждено
  аудитом; перепроверить на свежем main).

## Изменения по файлам

- `pyproject.toml` — bump `version` `0.11.1` → `0.12.0`.
- `CHANGELOG.md` — добавить секцию `## [0.12.0] — 2026-..-..` с описанием:
  periodic subdomain monitoring (ADR 038) — toggle `track_subdomains`
  (opt-in, default off), сигналы new/removed, per-user/per-domain интервал,
  scheduler по образцу SSL, fan-out-уведомления, UX-конфигуратор + FSM
  интервала. Также отметить фиксы из аудита: устойчивость fan-out
  (без N+1, дедуп toggle'ов — TASK-0035), html.escape в нотификациях +
  верхний кап интервала проверки (TASK-0037). Перенести содержимое из
  `[Unreleased]`.
- (опц.) `docs/`/`STATE.md` — отметить релиз.

## Миграции БД

Новых не требуется — миграция `20260530_subdomain_monitor` уже на main
(влита в TASK-0027). Релиз только тегирует.

## Инварианты (защитить тестами)

- Не вводит новой логики — релизный таск. Тесты подсистемы закрыты в
  TASK-0033/0034.

## Definition of Done

- [ ] Предусловия выше выполнены (0033/0034/0035/0037 в main, CI зелёный)
- [ ] `pyproject` bump 0.11.1 → 0.12.0
- [ ] Секция `[0.12.0]` в `CHANGELOG.md`
- [ ] Аннотированный тег `v0.12.0` на актуальном main
- [ ] Деплой (`bash scripts/deploy.sh`); v0.11.1 в проде, если ещё не катился
- [ ] `handoff.py validate` проходит; STATE.md обновлён
- [ ] PR открыт по шаблону, CI зелёный

## Ссылки

- ADR: `docs/decisions.md` (ADR 037, 038)
- Аудит: `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
- Блокеры (все в v0.12.0): TASK-0033 ✅, TASK-0034 ✅, TASK-0035, TASK-0037
- Образец релизного таска: TASK-0014
