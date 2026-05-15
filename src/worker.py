"""Worker / Scheduler entrypoint placeholder.

Будет заменён на ARQ-воркер на Этапе 4. Один и тот же модуль запускается
двумя контейнерами docker-compose:

- ``python -m src.worker``               → обычный воркер
- ``python -m src.worker --scheduler``   → планировщик периодических задач

Заглушка различает роли только текстом сообщения, флаг ``--scheduler``
больше нигде не используется. Реальная реализация: см. TODO.md, Этап 4.
"""

from __future__ import annotations

import asyncio
import sys


async def _idle() -> None:
    """Печатает маркер с ролью и блокируется навсегда."""
    role = "Scheduler" if "--scheduler" in sys.argv else "Worker"
    print(f"{role} entrypoint placeholder. Will be implemented in Stage 4.", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_idle())
