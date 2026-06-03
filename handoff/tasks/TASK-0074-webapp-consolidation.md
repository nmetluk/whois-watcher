---
id: TASK-0074
title: WebApp — консолидация 0066–0070 в одну сборочную ветку (v0.16)
status: done
milestone: v0.16.0
adr: 043
area: code
depends_on: [TASK-0073]
branch: task/0074-webapp-consolidation
owner: grok-4.3
session: docs/sessions/2026-06-09_task-0074-webapp-consolidation.md
pr: https://github.com/nmetluk/whois-watcher/pull/49
created: 2026-06-09
---

# TASK-0074 — Консолидация WebApp в одну ветку (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Заменяет параллельные ветки 0066–0070** (см. «Корень проблемы»).

## Корень проблемы

0066–0070 были сделаны как **5 независимых одиночных коммитов от main**, каждый
**заново** переписывает общие файлы фронта по-разному → они не складываются:
- `0066` = backend read-API; `0070` = backend read+write + фронт-фундамент
  **без экранов**; `0067` = фундамент; `0068` = фундамент + компоненты
  (Check/GroupTag/IRow/Ring/DomainRow) + экраны List/Domain; `0069` = фундамент
  + все 6 экранов, но **без** компонентов Check/GroupTag/IRow.
- Нет ни одной ветки с **полным консистентным** webapp; слияние подряд = конфликты
  во всех общих файлах (`App.tsx`/`main.tsx`/`vite.config`/`package.json`/стили/
  `Icon.tsx`) и почти наверняка **несборка**. Backend дублируется в 0066 и 0070.

## Цель

Собрать **ОДНУ** ветку поверх свежего `main`, содержащую цельный, **собираемый**
WebApp, и сдать как один PR. Исходный материал — содержимое веток 0066–0070
(переиспользовать, не писать с нуля), но привести к одному консистентному дереву.

## Что должна содержать ветка (единое и согласованное)

**Backend** (`src/bot/webapp/`): один модуль — `auth.py` (валидация initData по
точному алгоритму, см. TASK-0066), `api.py` (read **и** write эндпойнты:
portfolio/domain/dashboard/calendar/alerts/settings/groups/wishlist + тогглы/
add/remove/массовые/настройки/импорт/mark-read), регистрация в
`src/bot/webhook.py`. Хэндлеры тонкие → сервисы; ownership/PII-скоуп; лимиты;
`audit()` на действия. (Свести read из 0066 и write из 0070 в одно.)

**Frontend** (`webapp/`, Vite+React-TS): один фундамент (App.tsx с навигацией/
табами/стеком/MainButton/BackButton/тема, main.tsx, vite/tsconfig/package,
токены `tokens.css`/`tg-chrome.css`, API-клиент с initData) + **ВСЕ** компоненты
(Icon, Ring, Check, GroupTag, IRow, DomainRow и др.) + **ВСЕ 6 экранов**
(List, Domain, Dashboard, Calendar, Alerts, More) + подключённые write-действия
(optimistic+toast). Никакого unpkg/Babel/рамки телефона/сид-данных.

**Группы** — после TASK-0073 (схема): подключить группировку; до него —
graceful-degrade (без групп), не ссылаться на несуществующую модель.

## Definition of Done

- [ ] Одна ветка/PR; backend read+write+auth консистентны; фронт — фундамент +
      все компоненты + все 6 экранов + действия, **внутренне согласовано**
- [ ] **`vite build` проходит** (фронт реально собирается; нет битых импортов)
- [ ] **Полный backend `pytest` зелёный**; `ruff`/`black`/`mypy`; фронт линт/тайпчек
- [ ] Реальная проверка mini-app в Telegram — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `design/webapp/v1/`; ветки `task/0066…0070` (исходный материал);
  TASK-0073 (группы).
