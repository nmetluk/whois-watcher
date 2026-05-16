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

from arq.worker import run_worker

from src.config.settings import get_settings
from src.observability import setup_logging, setup_sentry
from src.tasks.arq_config import WorkerSettings


def main() -> None:
    """Поднимает structlog/Sentry и запускает воркер."""
    settings = get_settings()
    # Тот же шаблон, что в src.main: один источник истины для observability.
    setup_logging(settings)
    setup_sentry(settings)
    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
