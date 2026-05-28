#!/usr/bin/env python3
"""Кроссплатформенный CLI управления handoff-задачами.

Источник правды по процессу — ``handoff/README.md``. Этот скрипт
автоматизирует рутину, чтобы исполнитель и архитектор не вводили
команды руками: создание задач, доску ``handoff/INDEX.md``, смену
статуса, валидацию для CI, скелет аудита.

Зависимостей нет — только стандартная библиотека (работает на
Windows/macOS/Linux, Python 3.11+). Не импортирует код проекта.

Примеры:
    python scripts/handoff.py new --title "Багфикс wishlist" --milestone v0.8.1 --adr 034
    python scripts/handoff.py list --status open
    python scripts/handoff.py board
    python scripts/handoff.py claim TASK-0001 --owner claude-code
    python scripts/handoff.py status TASK-0001 in_review
    python scripts/handoff.py done TASK-0001
    python scripts/handoff.py validate
    python scripts/handoff.py audit --section "v0.9.0 поддомены"
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

# --- расположение в репозитории -------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "handoff"
TASKS_DIR = HANDOFF / "tasks"
AUDITS_DIR = HANDOFF / "audits"
TEMPLATES_DIR = HANDOFF / "templates"
INDEX_FILE = HANDOFF / "INDEX.md"
SESSIONS_DIR = ROOT / "docs" / "sessions"

ALLOWED_STATUS = ("open", "claimed", "in_review", "blocked", "done")
ALLOWED_AREA = ("code", "docs", "infra", "audit")
TASK_RE = re.compile(r"^TASK-(\d{4})$")

# Поля frontmatter задачи в стабильном порядке.
TASK_FIELDS = (
    "id",
    "title",
    "status",
    "milestone",
    "adr",
    "area",
    "depends_on",
    "branch",
    "owner",
    "session",
    "pr",
    "created",
    "blocked_reason",
)

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


# --- мини-парсер frontmatter ----------------------------------------------
def _parse_value(raw: str) -> object:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    return raw


def _dump_value(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    text = str(value)
    if text == "":
        return '""'
    return text


def read_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    """Возвращает (frontmatter, body). Без frontmatter → ({}, весь текст)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta: dict[str, object] = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        meta[key.strip()] = _parse_value(raw)
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return meta, body


def write_task(path: Path, meta: dict[str, object], body: str) -> None:
    out = ["---"]
    for key in TASK_FIELDS:
        if key in meta:
            out.append(f"{key}: {_dump_value(meta[key])}")
    # неизвестные ключи — сохраняем в конце, чтобы ничего не терять
    for key, val in meta.items():
        if key not in TASK_FIELDS:
            out.append(f"{key}: {_dump_value(val)}")
    out.append("---")
    out.append("")
    out.append(body.rstrip("\n"))
    out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


# --- утилиты ---------------------------------------------------------------
def slugify(title: str) -> str:
    text = "".join(_CYR.get(ch, ch) for ch in title.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "task"


def iter_task_files() -> list[Path]:
    if not TASKS_DIR.exists():
        return []
    return sorted(p for p in TASKS_DIR.glob("TASK-*.md"))


def load_tasks() -> list[dict[str, object]]:
    tasks = []
    for path in iter_task_files():
        meta, _ = read_frontmatter(path)
        meta["_path"] = str(path.relative_to(ROOT))
        tasks.append(meta)
    return tasks


_ID_IN_NAME = re.compile(r"^TASK-(\d{4})")


def next_id() -> str:
    nums = [
        int(m.group(1)) for p in iter_task_files() if (m := _ID_IN_NAME.match(p.stem))
    ]
    return f"TASK-{(max(nums) + 1) if nums else 1:04d}"


def find_task(task_id: str) -> Path:
    matches = list(TASKS_DIR.glob(f"{task_id}-*.md"))
    if not matches:
        sys.exit(f"error: задача {task_id} не найдена в {TASKS_DIR}")
    return matches[0]


def _git(args: list[str]) -> bool:
    try:
        subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        print(f"  git {' '.join(args)} → пропущено ({exc})")
        return False


# --- render INDEX ----------------------------------------------------------
def render_index() -> str:
    tasks = load_tasks()
    order = {s: i for i, s in enumerate(ALLOWED_STATUS)}
    tasks.sort(key=lambda t: (order.get(str(t.get("status")), 99), str(t.get("id"))))
    lines = [
        "# INDEX — доска задач",
        "",
        "> АВТО-генерируется `python scripts/handoff.py board`. Не править руками.",
        "",
        f"Всего задач: {len(tasks)}",
        "",
        "| ID | Статус | Майлстоун | ADR | Область | Тема | Ветка |",
        "|----|--------|-----------|-----|---------|------|-------|",
    ]
    for t in tasks:
        lines.append(
            "| {id} | {status} | {ms} | {adr} | {area} | {title} | {branch} |".format(
                id=t.get("id", "?"),
                status=t.get("status", "?"),
                ms=t.get("milestone", "") or "—",
                adr=t.get("adr", "") or "—",
                area=t.get("area", "") or "—",
                title=t.get("title", ""),
                branch=t.get("branch", "") or "—",
            )
        )
    lines.append("")
    return "\n".join(lines)


# --- команды ---------------------------------------------------------------
def cmd_new(args: argparse.Namespace) -> int:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    tid = next_id()
    slug = args.slug or slugify(args.title)
    path = TASKS_DIR / f"{tid}-{slug}.md"
    tmpl_path = TEMPLATES_DIR / "task.md"
    _, body = read_frontmatter(tmpl_path) if tmpl_path.exists() else ({}, "")
    body = body.replace("TASK-NNNN", tid).replace("NNNN", tid.split("-")[1])
    meta: dict[str, object] = {
        "id": tid,
        "title": args.title,
        "status": "open",
        "milestone": args.milestone or "",
        "adr": args.adr or "",
        "area": args.area,
        "depends_on": args.depends.split(",") if args.depends else [],
        "branch": "",
        "owner": "",
        "session": "",
        "pr": "",
        "created": dt.date.today().isoformat(),
    }
    write_task(path, meta, body or f"# {tid} — {args.title}\n")
    INDEX_FILE.write_text(render_index(), encoding="utf-8")
    print(f"создан {path.relative_to(ROOT)}")
    print("заполни тело по шаблону, затем: git add handoff/ && git commit && git push")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    if args.status:
        tasks = [t for t in tasks if str(t.get("status")) == args.status]
    if args.milestone:
        tasks = [t for t in tasks if str(t.get("milestone")) == args.milestone]
    if not tasks:
        print("(нет задач под фильтром)")
        return 0
    for t in tasks:
        print(
            f"{t.get('id'):10} [{str(t.get('status')):9}] "
            f"{t.get('milestone') or '—':8} {t.get('title')}"
        )
    return 0


def cmd_board(_: argparse.Namespace) -> int:
    HANDOFF.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(render_index(), encoding="utf-8")
    print(f"обновлён {INDEX_FILE.relative_to(ROOT)}")
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    path = find_task(args.task)
    meta, body = read_frontmatter(path)
    tid = str(meta.get("id"))
    slug = path.stem.split("-", 2)[2] if path.stem.count("-") >= 2 else "task"
    branch = f"task/{tid.split('-')[1]}-{slug}"
    meta["status"] = "claimed"
    meta["owner"] = args.owner or meta.get("owner") or ""
    meta["branch"] = branch
    write_task(path, meta, body)
    INDEX_FILE.write_text(render_index(), encoding="utf-8")
    print(f"{tid} → claimed, ветка {branch}")
    if not args.no_git:
        _git(["checkout", "-b", branch])
    else:
        print(f"  создай ветку вручную: git checkout -b {branch}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if args.value not in ALLOWED_STATUS:
        sys.exit(f"error: статус должен быть из {ALLOWED_STATUS}")
    if args.value == "blocked" and not args.reason:
        sys.exit("error: для status=blocked обязателен --reason")
    path = find_task(args.task)
    meta, body = read_frontmatter(path)
    meta["status"] = args.value
    if args.value == "blocked":
        meta["blocked_reason"] = args.reason
    if args.session:
        meta["session"] = args.session
    if args.pr:
        meta["pr"] = args.pr
    write_task(path, meta, body)
    INDEX_FILE.write_text(render_index(), encoding="utf-8")
    print(f"{meta.get('id')} → {args.value}")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    path = find_task(args.task)
    meta, body = read_frontmatter(path)
    meta["status"] = "done"
    write_task(path, meta, body)
    INDEX_FILE.write_text(render_index(), encoding="utf-8")
    print(f"{meta.get('id')} → done")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    slug = slugify(args.section)
    report = AUDITS_DIR / f"AUDIT-{today}-{slug}.md"
    tmpl = TEMPLATES_DIR / "audit.md"
    content = tmpl.read_text(encoding="utf-8") if tmpl.exists() else "# AUDIT\n"
    content = content.replace("YYYY-MM-DD", today).replace(
        "<раздел / майлстоун>", args.section
    )
    report.write_text(content, encoding="utf-8")
    # сопутствующий аудит-таск
    ns = argparse.Namespace(
        title=f"Аудит: {args.section}",
        slug=None,
        milestone=args.milestone or "",
        adr="",
        area="audit",
        depends=None,
    )
    cmd_new(ns)
    print(f"создан отчёт {report.relative_to(ROOT)}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    errors: list[str] = []
    seen: set[str] = set()
    ids: set[str] = {str(t.get("id")) for t in load_tasks()}
    for path in iter_task_files():
        rel = path.relative_to(ROOT)
        meta, _body = read_frontmatter(path)
        tid = str(meta.get("id", ""))
        if not TASK_RE.match(tid):
            errors.append(f"{rel}: невалидный id {tid!r}")
            continue
        if not path.stem.startswith(tid):
            errors.append(f"{rel}: имя файла не начинается с {tid}")
        if tid in seen:
            errors.append(f"{rel}: дублирующийся id {tid}")
        seen.add(tid)
        status = str(meta.get("status", ""))
        if status not in ALLOWED_STATUS:
            errors.append(f"{rel}: статус {status!r} не из {ALLOWED_STATUS}")
        area = str(meta.get("area", ""))
        if area and area not in ALLOWED_AREA:
            errors.append(f"{rel}: область {area!r} не из {ALLOWED_AREA}")
        for dep in meta.get("depends_on", []) or []:
            if str(dep) not in ids:
                errors.append(f"{rel}: depends_on ссылается на несуществующий {dep}")
        if status == "done":
            session = str(meta.get("session", ""))
            if not session:
                errors.append(f"{rel}: status=done без session-отчёта")
            elif not (ROOT / session).exists():
                errors.append(f"{rel}: session-файл не найден: {session}")
        if status == "blocked" and not meta.get("blocked_reason"):
            errors.append(f"{rel}: status=blocked без blocked_reason")
    # свежесть INDEX
    current = INDEX_FILE.read_text(encoding="utf-8") if INDEX_FILE.exists() else ""
    if current != render_index():
        errors.append("handoff/INDEX.md устарел — запусти: python scripts/handoff.py board")
    if errors:
        print("VALIDATE: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"VALIDATE: OK ({len(seen)} задач)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="handoff", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pn = sub.add_parser("new", help="создать задачу")
    pn.add_argument("--title", required=True)
    pn.add_argument("--slug", default=None)
    pn.add_argument("--milestone", default=None)
    pn.add_argument("--adr", default=None)
    pn.add_argument("--area", default="code", choices=ALLOWED_AREA)
    pn.add_argument("--depends", default=None, help="через запятую: TASK-0001,TASK-0002")
    pn.set_defaults(func=cmd_new)

    pl = sub.add_parser("list", help="список задач")
    pl.add_argument("--status", default=None, choices=ALLOWED_STATUS)
    pl.add_argument("--milestone", default=None)
    pl.set_defaults(func=cmd_list)

    pb = sub.add_parser("board", help="пересобрать INDEX.md")
    pb.set_defaults(func=cmd_board)

    pc = sub.add_parser("claim", help="взять задачу в работу")
    pc.add_argument("task")
    pc.add_argument("--owner", default=None)
    pc.add_argument("--no-git", action="store_true", help="не создавать ветку git")
    pc.set_defaults(func=cmd_claim)

    ps = sub.add_parser("status", help="сменить статус")
    ps.add_argument("task")
    ps.add_argument("value", choices=ALLOWED_STATUS)
    ps.add_argument("--reason", default=None, help="для status=blocked")
    ps.add_argument("--session", default=None)
    ps.add_argument("--pr", default=None)
    ps.set_defaults(func=cmd_status)

    pd = sub.add_parser("done", help="отметить выполненной")
    pd.add_argument("task")
    pd.set_defaults(func=cmd_done)

    pa = sub.add_parser("audit", help="скелет аудита + аудит-таск")
    pa.add_argument("--section", required=True)
    pa.add_argument("--milestone", default=None)
    pa.set_defaults(func=cmd_audit)

    pv = sub.add_parser("validate", help="валидация задач для CI")
    pv.set_defaults(func=cmd_validate)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
