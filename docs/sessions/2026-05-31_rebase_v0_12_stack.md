# Session 2026-05-31 — Ребейз стека v0.12 (0027-0029) на свежий main

## Цель

Разблокировать застрявший стек веток v0.12 (мониторинг поддоменов, ADR 038):
- `task/0027-subdomain-monitor-schema`
- `task/0028-subdomain-monitor-diff-scheduler`
- `task/0029-subdomain-monitor-notify-ux`

Ветки были Based на старом коммите `552fbbd` (ADR 038 design), а main ушёл вперёд
на 12 коммитов (релиз v0.11.1, ADR 039 — отдельная таблица wishlist).

## Что сделал

### 1. Обновление local main

```bash
git checkout main && git pull --rebase origin main
```

local main был уже синхронизирован с origin/main.

### 2. Ребейз стека

```bash
git checkout task/0029-subdomain-monitor-notify-ux
git rebase --update-refs --onto origin/main 552fbbd
```

При ребейзе несколько коммитов ADR 039 (TASK-0031/0032) уже были на main,
поэтому их skip'нул:
- `5285b7d` design(ADR 039)
- `33a8651` feat(TASK-0031/0032)
- `fdc18dc` docs(TASK-0031/0032)
- `dd7a262` tests(TASK-0031/0032)
- `879c290` chore(handoff)
- `2959621` docs(session)
- `92c0624` fix(migration)
- `a2298b6` fix(list)
- `9b0c940` handoff: TASK-0031/0032 → done
- `7c1ed85` state: релиз v0.11.1

Ребайз прошёл, но `--update-refs` сломал структуру — все три ветки указывали
на один и тот же коммит (HEAD task/0029). Исправил вручную:

```bash
git checkout task/0027-subdomain-monitor-schema
git reset --hard 289105e  # docs(TASK-0027): update PR #19

git checkout task/0028-subdomain-monitor-diff-scheduler
git reset --hard 32508a9  # docs(TASK-0028): update PR #20
```

task/0029 уже была правильной (`f888d96` — latest commit).

### 3. Проверка после ребейза

**Anti-drift check:**
```bash
grep -rn is_wishlist src tests
```
Результат: есть только как параметр функции в scheduler/handlers (не колонка модели).
В `src/db/models.py` колонки `is_wishlist` НЕТ — правильно.

**Migration check:**
```bash
uv run alembic heads
```
Результат: `20260530_subdomain_monitor (head)` — ровно один head.

down_revision в `20260530_0001_add_subdomain_monitor_toggles_and_user_interval.py`
указывает на `20260530_wishlist` — правильно.

**keyboards.py:**
- Поддоменные toggle'ы есть (`track_subdomains`, `notify_subdomain_new`,
  `notify_subdomain_removed`, `edit_subdomain_interval`)
- wishlist filter из `list_filters` удалён (ADR 039)
- wishlist кнопки в `whois_actions` есть (ADR 039)

**domains.py:**
- Wishlist методы удалены (ADR 039)

**Локали:**
- Поддоменные ключи есть в `ru.py` и `en.py`

### 4. Тесты и линтеры

```bash
uv run pytest tests/ -x --tb=short
```
Результат: 902 passed, 1 skipped — всё зелёное.

```bash
uv run ruff check src tests
uv run black --check src tests
uv run mypy src
```
Результат: все проверки прошли.

### 5. Push и handoff

```bash
uv run python scripts/handoff.py board
git add handoff/INDEX.md
git commit -m "chore(handoff): regen INDEX after rebase"
git push --force-with-lease origin task/0027-subdomain-monitor-schema \
  task/0028-subdomain-monitor-diff-scheduler task/0029-subdomain-monitor-notify-ux
```

```bash
uv run python scripts/handoff.py status TASK-0027 in_review
```

## Итог

Стек v0.12 успешно ребейзнут на свежий origin/main:
- 0027 → 0028 → 0029 (правильная вложенность)
- Тесты зелёные
- TASK-0027 переведён в `in_review`
- PR #19 готов к ревью архитектором

## Что дальше

1. Архитектор ревьюит и мержит PR #19 (TASK-0027)
2. После мержа — ревью PR #20 (TASK-0028)
3. После мержа — ревью PR #21 (TASK-0029)
4. TASK-0030 — комплексный аудит v0.12
5. Релиз v0.12.0
