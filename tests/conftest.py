"""Глобальные фикстуры тестов.

Сейчас минимальный конфиг — добавляем фикстуры по мере появления нужды
(БД-сессии будут в integration-тестах на Этапе 4).
"""

from __future__ import annotations

import os

# Подставляем безопасные дефолты для тестов: иначе ``get_settings`` упадёт
# на отсутствии обязательных переменных (BOT_TOKEN, WEBHOOK_*, POSTGRES_PASSWORD).
# Это поведение per-module: переменные ставятся ДО импорта тестов pytest'ом.
os.environ.setdefault("BOT_TOKEN", "test-bot-token")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://test.local")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("POSTGRES_PASSWORD", "test-postgres-password")
