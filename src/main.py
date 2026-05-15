"""Bot entrypoint placeholder.

Будет заменён на полноценный webhook-сервер aiogram на Этапе 2.
Пока модуль нужен только для того, чтобы:

- собирался Docker-образ (Dockerfile CMD ["python", "-m", "src.main"])
- контейнер `bot` в docker-compose стартовал и оставался запущенным

Реальная реализация: см. TODO.md, Этап 2.
"""

from __future__ import annotations

import asyncio


async def _idle() -> None:
    """Печатает маркер и блокируется навсегда, чтобы контейнер не завершился."""
    print("Bot entrypoint placeholder. Will be implemented in Stage 2.", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_idle())
