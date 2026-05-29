---
id: TASK-0006
title: Комплексный аудит v0.9.0 (поддомены/PSL)
status: done
milestone: v0.9.0
adr: 035
area: audit
depends_on: [TASK-0005]
branch: ""
owner: ""
session: "docs/sessions/2026-05-29_audit-v0-9-0.md"
pr: ""
created: 2026-05-29
---

# TASK-0006 — Комплексный аудит v0.9.0 (поддомены / PSL)

> Выполняется в **отдельной сессии** после merge всех тасков v0.9.0
> (2a–2d). Правило процесса — `handoff/README.md` (аудит после крупного
> раздела). Шаблон отчёта — `handoff/templates/audit.md`.

## Цель

Независимая проверка раздела «поддомены/PSL» по направлениям
безопасности, архитектуры, производительности, тестов,
кроссплатформенности и документации. Findings → новые таски.

## Как запустить

```
python scripts/handoff.py audit --section "v0.9.0 поддомены/PSL" --milestone v0.9.0
```
(создаст отчёт `handoff/audits/AUDIT-YYYY-MM-DD-*.md`)

## Фокус именно этого аудита

- **Безопасность / supply-chain:** новая зависимость `tldextract` — пин,
  источник, что bundled snapshot не тянет сеть в рантайме; нет утечки
  PSL-кэша/путей в логи.
- **Архитектура:** соответствие ADR 035; WHOIS keyed по registrable,
  DNS/SSL — по поддомену; общий `whois_cache`-row на родителя (ADR 006
  не нарушен); нет дублирующих whois_cache-строк.
- **Производительность:** парс домена синхронный без сети; нет N+1 в
  переключённых джойнах; индекс `ix_user_domains_registrable` используется.
- **Тесты:** покрыты registrable/edge-кейсы (IDN, многоуровневые зоны),
  миграция, отсутствие ложной «свободы» поддомена.
- **Кроссплатформенность:** оффлайн-инициализация tldextract, `cache_dir`
  без хардкода путей/разделителей.
- **Документация:** ADR 035, CLAUDE.md, STATE актуальны коду.

## Definition of Done

- [ ] Отчёт `handoff/audits/AUDIT-*.md` заполнен по всем направлениям
- [ ] Каждый finding оформлен как новый TASK с серьёзностью
- [ ] Резюме go / fix-then-go / stop зафиксировано
- [ ] STATE.md обновлён итогом аудита
- [ ] `python scripts/handoff.py validate` проходит

## Ссылки

- ADR 035, `handoff/templates/audit.md`, `docs/workflow.md` (раздел аудита)
- Зависит от: TASK-0005
