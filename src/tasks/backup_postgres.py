"""ARQ-задача `backup_postgres`: ежечасный бекап Postgres (ADR 042, TASK-0058).

- pg_dump через `asyncio.create_subprocess_exec` (аргументы списком, без shell).
- Пароль только через env `PGPASSWORD` (не в командной строке/логах).
- Формат custom `-Fc`, файл `ww-YYYYMMDD-HHMMSS.dump`.
- Verify: rc==0 + size > порог + `pg_restore --list` rc==0.
- Ротация: оставить ровно `BACKUP_KEEP` свежих по mtime.
- Статус в Redis `ops:last_backup` (через `ctx["sync_redis"]`) для TASK-0059.
- Никогда не бросает: возвращает dict-статус, логирует.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import Redis as AsyncRedis

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Разумный таймаут на дамп (10 мин); большие БД можно подкрутить позже.
_BACKUP_TIMEOUT_SECONDS = 600


async def backup_postgres(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ cron: pg_dump + verify + rotate + write status to Redis.

    Вызывается по cron `minute={0}` из scheduler-контейнера.
    """
    settings: Settings = ctx.get("settings") or get_settings()
    redis: AsyncRedis[str] | None = ctx.get("sync_redis") or ctx.get("redis")

    backup_dir = Path(settings.backup_dir).resolve()
    ts = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    dump_path = backup_dir / f"ww-{ts}.dump"

    status: dict[str, Any] = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "ok": False,
        "size": 0,
        "path": str(dump_path),
        "error": None,
    }

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.exception("backup_postgres: cannot create BACKUP_DIR %s", backup_dir)
        status["error"] = f"mkdir failed: {e}"
        await _write_status(redis, status)
        return {"status": "error", **status}

    pg_password = settings.postgres_password.get_secret_value()
    env = os.environ.copy()
    env["PGPASSWORD"] = pg_password

    logger.info("backup_postgres: starting pg_dump to %s", dump_path)

    rc = -1
    stderr = b""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-h",
            settings.postgres_host,
            "-p",
            str(settings.postgres_port),
            "-U",
            settings.postgres_user,
            "-d",
            settings.postgres_db,
            "-Fc",
            "-f",
            str(dump_path),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=_BACKUP_TIMEOUT_SECONDS)
        rc = proc.returncode if proc.returncode is not None else -1
    except TimeoutError:
        logger.error("backup_postgres: pg_dump timed out after %ds", _BACKUP_TIMEOUT_SECONDS)
        status["error"] = "timeout"
        # Попытаться убить если процесс висит (proc может быть не определён)
    except Exception as exc:
        logger.exception("backup_postgres: pg_dump subprocess failed")
        status["error"] = f"subprocess error: {exc}"

    # Verify
    size = 0
    if rc == 0 and dump_path.exists():
        try:
            size = dump_path.stat().st_size
        except Exception:
            size = 0

        min_bytes = getattr(settings, "backup_min_bytes", 1024)
        if size < min_bytes:
            status["error"] = f"dump too small: {size} bytes < {min_bytes}"
        else:
            # pg_restore --list для custom формата (-Fc)
            try:
                vproc = await asyncio.create_subprocess_exec(
                    "pg_restore",
                    "--list",
                    str(dump_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, v_err = await asyncio.wait_for(vproc.communicate(), timeout=60)
                if vproc.returncode == 0:
                    status["ok"] = True
                else:
                    status["error"] = (
                        f"pg_restore --list rc={vproc.returncode} "
                        f"{v_err.decode(errors='ignore')[:300]}"
                    )
            except Exception as ve:
                status["error"] = f"verify error: {ve}"
    else:
        if status["error"] is None:
            status["error"] = f"pg_dump rc={rc} {stderr.decode(errors='ignore')[:300]}"

    status["size"] = size

    # Ротация (даже если дамп упал — чистим старьё)
    keep = getattr(settings, "backup_keep", 36)
    try:
        all_dumps = sorted(
            backup_dir.glob("ww-*.dump"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        for old in all_dumps[keep:]:
            try:
                old.unlink()
                logger.debug("backup_postgres: rotated (deleted) %s", old)
            except Exception as ue:
                logger.warning("backup_postgres: failed to unlink %s: %s", old, ue)
        logger.info(
            "backup_postgres: rotation done, kept <=%d out of %d candidates",
            keep,
            len(all_dumps),
        )
    except Exception:
        logger.exception("backup_postgres: rotation failed (non-fatal)")

    # Статус для ежечасного отчёта (TASK-0059)
    await _write_status(redis, status)

    if status["ok"]:
        logger.info("backup_postgres: SUCCESS path=%s size=%d", dump_path, size)
    else:
        logger.error("backup_postgres: FAILED error=%s", status["error"])

    return {"status": "success" if status["ok"] else "failed", **status}


async def _write_status(redis: AsyncRedis[str] | None, status: dict[str, Any]) -> None:
    if redis is None:
        logger.warning("backup_postgres: no redis in ctx, cannot write ops:last_backup")
        return
    try:
        await redis.set("ops:last_backup", json.dumps(status, ensure_ascii=False), ex=7200)
    except Exception:
        logger.exception("backup_postgres: failed to SET ops:last_backup (non-fatal)")


__all__ = ["backup_postgres"]
