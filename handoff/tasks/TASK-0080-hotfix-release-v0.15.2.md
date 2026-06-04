---
id: TASK-0080
title: Хотфикс-релиз v0.15.2 (DNS-сбой ≠ «нет записей» в email-слое)
status: open
milestone: v0.15.2
adr: 040
area: docs
depends_on: [TASK-0079]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-09
---

# TASK-0080 — Хотфикс-релиз v0.15.2

> Архитекторский релиз-таск. Стартовать только после merge TASK-0079.
> ⚠️ Merge/тег — **только архитектор**, прямой push в `main` запрещён
> (см. инцидент v0.15.1).

## Шаги

- [ ] Подтвердить merge TASK-0079 в `main`, зелёный CI
- [ ] Bump `pyproject.toml` → `0.15.2`
- [ ] `CHANGELOG.md` — секция `[0.15.2]` (Fixed):
      - email-слой больше не трактует DNS-сбой (timeout/no-nameservers) как
        «нет записей» — карточка показывает «не отвечает», а не ложное «MX нет»;
      - конфигурируемые DNS-резолверы через `DNS_NAMESERVERS` (дефолт —
        системный resolver); диагностика-логи сбоев.
- [ ] Тег `v0.15.2`, GitHub Release (текст готовит архитектор)
- [ ] Обновить `handoff/STATE.md`, `TODO.md`, `handoff/INDEX.md`

## Definition of Done

- [ ] Тег + релиз опубликованы; STATE/TODO/INDEX актуальны
- [ ] Возврат к webapp-цепочке (0073 → 0071 → 0072)
