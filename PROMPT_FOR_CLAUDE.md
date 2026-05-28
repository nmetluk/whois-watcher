# DEPRECATED — workflow перенесён

Прежний процесс (ручной промпт + Telegram-пинг + монолитный
`SESSION_LOG.md`) заменён на **handoff + PR** с GitHub как источником
правды.

Актуальные документы:

- **Контракт процесса (start here):** `handoff/README.md`
- **Подробный воркфлоу:** `docs/workflow.md`
- **Живое состояние проекта:** `handoff/STATE.md`
- **Доска задач:** `handoff/INDEX.md`
- **CLI управления задачами:** `scripts/handoff.py`

Per-session отчёты теперь в `docs/sessions/` (а не в `SESSION_LOG.md`,
который заморожен как исторический).

Файл оставлен как указатель и подлежит `git rm` после того, как все
ссылки на него вычищены.
