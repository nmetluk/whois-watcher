"""Конфигурация приложения через pydantic-settings.

Все значения читаются из переменных окружения (или из ``.env`` в dev).
Список переменных задокументирован в ``.env.example``.

Использование::

    from src.config.settings import get_settings

    settings = get_settings()
    dsn = settings.postgres_dsn

``get_settings()`` кеширован (``lru_cache``), так что в одном процессе
повторные вызовы возвращают тот же экземпляр.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import (
    Field,
    SecretStr,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Главный класс настроек.

    Конфигурация: ``.env`` (если есть), нечувствительные к регистру имена,
    лишние переменные игнорируются (не падаем на чужих env).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------
    bot_token: SecretStr = Field(
        ...,
        description="Токен бота от @BotFather.",
    )
    webhook_base_url: str = Field(
        ...,
        description="Публичный HTTPS URL без trailing slash. Пример: https://bot.example.com",
    )
    webhook_path: str = Field(
        "/webhook",
        description="Путь webhook. Должен начинаться с '/'.",
    )
    webhook_secret: SecretStr = Field(
        ...,
        description="Секрет для X-Telegram-Bot-Api-Secret-Token.",
    )
    webhook_host: str = Field(
        "0.0.0.0",  # слушаем все интерфейсы внутри docker-сети
        description="Хост, на котором слушает внутренний webhook-сервер.",
    )
    webhook_port: int = Field(
        8080,
        ge=1,
        le=65535,
        description="Порт внутреннего webhook-сервера.",
    )

    # ------------------------------------------------------------------
    # PostgreSQL
    # ------------------------------------------------------------------
    postgres_host: str = Field("postgres", description="Хост Postgres.")
    postgres_port: int = Field(5432, ge=1, le=65535)
    postgres_user: str = Field("whoiswatcher")
    postgres_password: SecretStr = Field(...)
    postgres_db: str = Field("whoiswatcher")

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_host: str = Field("redis")
    redis_port: int = Field(6379, ge=1, le=65535)
    redis_db: int = Field(0, ge=0, le=15)

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    admin_channel_id: int | None = Field(
        None,
        description="ID канала для алертов (например, -100xxxxxxxxxx). None — алерты выключены.",
    )
    # ``NoDecode`` нужен, чтобы env-источник передал сырую строку нашему
    # ``mode='before'`` валидатору, а не пытался сам JSON-парсить "" в list[int].
    admin_user_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        description="CSV-список Telegram ID администраторов. Пример: 12345,67890",
    )

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> object:
        """Разбирает строку 'a,b,c' в список int (env обычно строка)."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------
    sentry_dsn: str | None = Field(None, description="Sentry DSN. None — Sentry отключён.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field("INFO")
    environment: Literal["development", "production"] = Field("development")

    # ------------------------------------------------------------------
    # Defaults для новых пользователей
    # ------------------------------------------------------------------
    default_timezone: str = Field("Europe/Moscow", description="Дефолтная TZ нового пользователя.")
    default_language: Literal["ru", "en"] = Field("ru")
    default_notify_hour: int = Field(9, ge=0, le=23)

    # ------------------------------------------------------------------
    # Bot meta
    # ------------------------------------------------------------------
    bot_name: str = Field("Whois Watcher")
    bot_username: str = Field("", description="Username без '@'. Опционально.")

    # ------------------------------------------------------------------
    # WHOIS proxy gateway (Этап 10, ADR 028) — primary lookup path
    # ------------------------------------------------------------------
    # При ``whois_proxy_enabled=True`` бот ходит за WHOIS-данными через
    # HTTP/JSON API локального прокси (``WHOIS_PROXY_URL``). Прокси сам
    # выбирает upstream (RDAP / WHOIS:43 / выделенный RU-relay для
    # .ru/.рф/.su), кэширует положительные ответы 24ч. При недоступности
    # прокси (5xx / network / timeout) бот делает fallback на прямой
    # RDAP+WHOIS:43 lookup из ``src.whois.client.lookup_direct``.
    whois_proxy_enabled: bool = Field(
        True,
        description="Использовать ли локальный WHOIS proxy gateway (ADR 028).",
    )
    whois_proxy_url: str = Field(
        "http://127.0.0.1:8043",
        description="Base URL прокси без trailing slash. Внутренний адрес.",
    )
    whois_proxy_timeout_seconds: int = Field(
        15,
        ge=1,
        description="Таймаут одного запроса к прокси (включая ожидание upstream).",
    )
    whois_proxy_health_check_interval_seconds: int = Field(
        60,
        ge=10,
        description="Интервал для periodic /healthz-проверки (использует cron).",
    )

    # ------------------------------------------------------------------
    # WHOIS — direct fallback (используется когда прокси недоступен)
    # ------------------------------------------------------------------
    # ``NoDecode`` нужен, чтобы env-источник передал сырую строку нашему
    # ``mode='before'`` валидатору. Так мы сами нормализуем ключи к lowercase
    # и аккуратно обрабатываем пустую строку.
    whois_server_overrides: Annotated[dict[str, str], NoDecode] = Field(
        default_factory=dict,
        description=(
            "Override WHOIS-серверов по TLD. JSON-объект, например: "
            '{"ru":"whois.example.com"}. Ключи приводятся к lowercase. '
            "Полезно когда дефолтный сервер недоступен с конкретного хоста."
        ),
    )

    # Включает «referral following»: для thin-WHOIS реестров (Verisign .com/.net,
    # Afilias и т. п.) после первого ответа парсим ``Registrar WHOIS Server`` и
    # делаем второй запрос — он даёт полные данные регистрации. Полезно для
    # большинства .com/.net доменов. Если хостинг блокирует исходящий 43-порт
    # на внешние сервера, можно выключить.
    whois_referral_following: bool = Field(
        True,
        description=(
            "Делать ли второй WHOIS-запрос на ``Registrar WHOIS Server`` для "
            "thin-WHOIS реестров (.com/.net). True — полнее данные, +1 TCP."
        ),
    )

    @field_validator("whois_server_overrides", mode="before")
    @classmethod
    def _parse_whois_overrides(cls, value: object) -> object:
        """JSON-строка (env обычно строка) → dict[lowercase tld, server]."""
        if value is None or value == "":
            return {}
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"WHOIS_SERVER_OVERRIDES must be valid JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("WHOIS_SERVER_OVERRIDES must be a JSON object")
            return {str(k).lower(): str(v) for k, v in parsed.items()}
        if isinstance(value, dict):
            return {str(k).lower(): str(v) for k, v in value.items()}
        return value

    # ------------------------------------------------------------------
    # Вычисляемые свойства
    # ------------------------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn(self) -> str:
        """DSN для async-движка (asyncpg)."""
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """URL Redis для ARQ и rate limiter."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def webhook_url(self) -> str:
        """Полный публичный URL, который регистрируется в Telegram."""
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает синглтон настроек.

    Кешируется на уровне процесса. Для тестов можно вызвать
    ``get_settings.cache_clear()``.
    """
    # обязательные поля берутся из env через pydantic-settings
    return Settings()
