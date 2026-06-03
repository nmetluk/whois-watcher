"""Best-effort helper для записи в audit_log (ADR 042, TASK-0057).

Никогда не бросает — предназначен для вызова из горячих путей (ARQ-таски,
rate-limit, webhook, startup). Открывает свою сессию внутри.
"""

from __future__ import annotations

import logging
from typing import Any

from src.db.repositories import AuditLogRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)


async def audit(
    level: str,
    category: str,
    message: str,
    *,
    actor: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Записать инцидент в audit_log (best-effort).

    Пример категорий: task_failure, rate_limit, admin_action, webhook, startup, other.
    Уровни: info, warning, error, critical.

    В ``context`` НЕ класть секреты, контакты, заметки (ADR 019).
    """
    try:
        async with get_session() as session:
            repo = AuditLogRepository(session)
            await repo.record(
                level=level,
                category=category,
                message=message,
                actor=actor,
                context=context,
            )
    except Exception:  # - best-effort, не ломаем вызывающий код
        # Логируем на debug, чтобы не спамить при временных проблемах с БД/пулингом.
        # Основная ошибка (если есть) будет залогирована в месте вызова.
        logger.debug("audit() swallowed exception (best-effort, never raises)", exc_info=True)
