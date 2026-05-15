"""Конфигурируемые лимиты приложения.

Все значения можно переопределить env-переменными с тем же именем (case-insensitive),
например::

    MAX_DOMAINS_PER_USER=100000
    MAX_WHOIS_PER_MINUTE=30
    TTL_FAR_DAYS=14

Дефолты согласованы с ``docs/architecture.md`` (раздел "Адаптивный TTL")
и ``docs/decisions.md`` (ADR 007, 011).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Limits(BaseSettings):
    """Лимиты: rate-limit, WHOIS-таймауты, адаптивный TTL, FSM-таймауты."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Лимиты пользователя
    # ------------------------------------------------------------------
    max_domains_per_user: int = Field(
        50_000,
        ge=1,
        description="Максимум доменов в портфеле одного пользователя (ADR 011).",
    )
    max_add_per_hour: int = Field(
        100,
        ge=1,
        description="/add в час на пользователя.",
    )
    max_whois_per_minute: int = Field(
        20,
        ge=1,
        description="Запросов /whois в минуту на пользователя.",
    )
    max_downloads_per_day: int = Field(
        5,
        ge=1,
        description="/download в сутки на пользователя.",
    )
    max_domains_per_download: int = Field(
        5_000,
        ge=1,
        description="Максимум доменов в одном файле для /download.",
    )

    # ------------------------------------------------------------------
    # Force refresh
    # ------------------------------------------------------------------
    force_refresh_cooldown_hours: int = Field(
        24,
        ge=1,
        description="Cooldown для /check и кнопки 'Обновить' на пару (user, domain).",
    )

    # ------------------------------------------------------------------
    # WHOIS / RDAP
    # ------------------------------------------------------------------
    whois_timeout_seconds: int = Field(
        15,
        ge=1,
        description="Таймаут одного WHOIS/RDAP-запроса.",
    )
    max_concurrent_whois: int = Field(
        50,
        ge=1,
        description="Глобальный лимит конкурентных WHOIS-запросов воркеров.",
    )

    # ------------------------------------------------------------------
    # Адаптивный TTL (ADR 007, см. docs/architecture.md)
    # ------------------------------------------------------------------
    ttl_far_days: int = Field(30, ge=1, description="Интервал проверки при >90 дней до истечения.")
    ttl_mid_days: int = Field(7, ge=1, description="Интервал проверки при 30–90 дней.")
    ttl_near_days: int = Field(2, ge=1, description="Интервал проверки при 7–30 дней.")
    ttl_critical_days: int = Field(1, ge=1, description="Интервал проверки при <7 дней.")
    ttl_after_expiry_days: int = Field(
        45,
        ge=1,
        description="Сколько дней продолжать проверять домен после истечения.",
    )

    # ------------------------------------------------------------------
    # Уведомления о проблемах
    # ------------------------------------------------------------------
    fail_threshold_for_user_notice: int = Field(
        5,
        ge=1,
        description="Сколько подряд неудач WHOIS до уведомления пользователя.",
    )
    problem_notify_cooldown_days: int = Field(
        7,
        ge=1,
        description="Не слать уведомление о проблеме чаще, чем раз в N дней.",
    )

    # ------------------------------------------------------------------
    # FSM-таймауты
    # ------------------------------------------------------------------
    download_state_timeout_minutes: int = Field(
        5,
        ge=1,
        description="Таймаут FSM-состояния /download (ожидание файла).",
    )
    delete_me_confirm_timeout_minutes: int = Field(
        5,
        ge=1,
        description="TTL Redis-флага delete_pending:* (ADR 017).",
    )

    # ------------------------------------------------------------------
    # Дедупликация алертов (ADR 019)
    # ------------------------------------------------------------------
    alert_dedup_ttl_minutes: int = Field(
        10,
        ge=1,
        description="Окно дедупликации алертов в админ-канал.",
    )


@lru_cache(maxsize=1)
def get_limits() -> Limits:
    """Возвращает синглтон лимитов. Кеш per-process."""
    return Limits()
