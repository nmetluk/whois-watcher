#!/bin/bash
# scripts/send-session-log.sh
# Добавляет skeleton-запись в SESSION_LOG.md по шаблону.
# Запись вставляется после ПЕРВОЙ строки `---` (разделитель между
# intro-абзацами журнала и списком записей) — так intro остаётся
# на месте, а новая запись попадает в самый верх списка.

set -e

if [ -z "$1" ]; then
  echo "Usage: ./scripts/send-session-log.sh \"Короткое описание задачи\""
  exit 1
fi

DATE=$(date '+%Y-%m-%d %H:%M')
TASK="$1"
SESSION_LOG="SESSION_LOG.md"

if [ ! -f "$SESSION_LOG" ]; then
  echo "Error: $SESSION_LOG not found in current directory"
  exit 1
fi

TMP=$(mktemp)
cat > "$TMP" << EOF
## Session $DATE — $TASK

**Задача:**

**Выполнено:**
-

**Изменённые/новые файлы:**
-

**Коммиты:**
-

**Проверки:**
- pytest:
- mypy strict:
- ruff:

**Архитектурные решения / Открытые вопросы:**
-

**Затраченное время:** ~XX минут

---
EOF

# Insert skeleton after the FIRST line equal to "---" (the separator
# between journal intro and the list of session entries). Previously
# awk inserted right after line 1 (the H1), which pushed intro
# paragraphs below new entries — required manual layout cleanup
# every session. See SESSION_LOG.md entries for podetap 2 / 2b / 3.
awk -v tmpfile="$TMP" '
  /^---$/ && !inserted {
    print
    print ""
    while ((getline line < tmpfile) > 0) print line
    inserted = 1
    next
  }
  { print }
' "$SESSION_LOG" > "${SESSION_LOG}.new"

ORIGINAL_LINES=$(wc -l < "$SESSION_LOG")
NEW_LINES=$(wc -l < "${SESSION_LOG}.new")
if [ "$NEW_LINES" -le "$ORIGINAL_LINES" ]; then
  echo "Error: no '---' separator found in $SESSION_LOG (or insertion failed)."
  echo "       Expected the journal to have an intro section ended by a"
  echo "       '---' line, then session entries below."
  rm "${SESSION_LOG}.new" "$TMP"
  exit 1
fi

mv "${SESSION_LOG}.new" "$SESSION_LOG"
rm "$TMP"

echo "OK: skeleton entry added to $SESSION_LOG"
echo "Open the file and fill in details before commit."
echo ""
echo "Remember:"
echo "  - Run pytest and record test count"
echo "  - Run mypy and ruff"
echo "  - List commits with short SHAs"
