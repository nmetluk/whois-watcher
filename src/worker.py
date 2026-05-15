"""Entrypoint ARQ-воркера.

Запуск::

    python -m src.worker

В docker-compose тот же модуль может стартовать «как планировщик» — флаг
``--scheduler`` сейчас не нужен (cron-задача ``scheduler_tick`` живёт внутри
воркера, отдельный процесс-планировщик не запускаем). Флаг принимаем для
обратной совместимости с docker-compose, но игнорируем.

ARQ сам ставит обработчики SIGINT/SIGTERM для graceful shutdown.
"""

from __future__ import annotations

import logging
import sys

from arq.worker import run_worker

from src.config.settings import get_settings
from src.tasks.arq_config import WorkerSettings


def _setup_basic_logging() -> None:
    """Минимальный stdlib logging — структурированный structlog настроится
    в ``arq_config._on_startup`` через ctx по аналогии с ботом.
    """
    settings = get_settings()
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        level=settings.log_level,
        stream=sys.stderr,
    )


def main() -> None:
    _setup_basic_logging()
    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
