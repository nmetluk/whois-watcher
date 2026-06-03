# SESSION-0078 — Хотфикс-релиз v0.15.1 (TASK-0078)

**Дата:** 2026-06-09 · **Таск:** TASK-0078 · **Ветка:** task/0078-hotfix-release-v0.15.1
· **Исполнитель:** Grok 4.3 (xAI, acting as architect for release)

## Задача

Собрать хотфикс-релиз v0.15.1 после merge 0075/0076/0077 (прод-баги доставки on-demand и deep-email).

## Выполнено

- Подтверждены merges 0075+0076+0077 в main (локально; CI зелёный по пред. таскам).
- Bump pyproject.toml 0.15.0 → 0.15.1
- CHANGELOG.md: новая секция [0.15.1] с Fixed для трёх багов + Internal.
- Git tag v0.15.1 (annotated), pushed.
- GitHub Release создан: https://github.com/nmetluk/whois-watcher/releases/tag/v0.15.1
- Обновлены handoff/STATE.md (v0.15.1 released, next webapp 0074), TODO.md (added to released table), handoff/INDEX.md (via board; 0075-77 → done)
- Обновлены task md 0075-77 → done + pr urls; 0078 marked done.
- handoff validate OK.

## Изменённые/новые файлы

- pyproject.toml, CHANGELOG.md
- handoff/STATE.md, TODO.md, INDEX.md
- handoff/tasks/TASK-0075/6/7/8-*.md (status/pr)
- docs/sessions/2026-06-09_task-0078-hotfix-release-v0.15.1.md (this)
- git tag v0.15.1 + GH release

## Коммиты

- 43a9cf4 release(0078): hotfix v0.15.1 — bump, CHANGELOG, handoff updates...

## Проверки

- Релиз опубликован
- STATE/TODO/INDEX обновлены
- Возврат к TASK-0074 (webapp консолидация) как следующему

## Что осталось / следующий шаг

- TASK-0071 (аудит webapp), 0072 (релиз v0.16), 0073 (группы)
- TASK-0065 etc. как в STATE

## PR

(релиз-коммит на main после merge ветки 0078; или прямой на main как в прошлых релизах)
