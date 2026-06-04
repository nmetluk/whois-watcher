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

    # FSM (ADR 041, TASK-0050) — TTL for aiogram FSM states in Redis
    redis_fsm_ttl: int = Field(
        300,
        ge=1,
        description="TTL (seconds) for FSM states. Abandoned flows expire automatically.",
    )

    # ------------------------------------------------------------------
    # DENIC and similar registries (TASK-0051) — expiry hidden by registry
    # ------------------------------------------------------------------
    no_expiry_tlds: list[str] = Field(
        default_factory=lambda: ["de"],
        description=(
            "TLDs (suffixes) where the registry deliberately does not publish "
            "expiry date (e.g. DENIC .de). Used to show special '🔒 hidden by registry' "
            "marker in /list and whois card instead of generic 'no data'."
        ),
    )

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
    # Instance identification (ADR 019, TASK-0019)
    # ------------------------------------------------------------------
    instance_name: str = Field(
        "",
        description="Метка деплоя, напр. 'prod-admin'. Пустая строка — не используется.",
    )
    server_ip: str = Field(
        "",
        description="Публичный IP сервера, задаётся в .env каждого деплоя. Пустая строка — не используется.",
    )

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
    # WebApp (Telegram mini-app, ADR 043, TASK-0066)
    # ------------------------------------------------------------------
    webapp_origin: str = Field(
        "",
        description=(
            "Allowed Origin for CORS on /api/webapp endpoints (e.g. https://web.telegram.org). "
            "If set, only this origin is allowed (plus no-origin for server-side). "
            "Empty = no extra CORS restriction (or same-origin)."
        ),
    )
    webapp_initdata_ttl: int = Field(
        3600,
        ge=60,
        le=604800,
        description="Max age (seconds) of Telegram initData 'auth_date' for replay protection. Default 1h (replay window).",
    )

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

    # ------------------------------------------------------------------
    # RIR/ASN lookup gateway (Этап 13, ADR 031)
    # ------------------------------------------------------------------
    # HTTP-клиент к локальному rir2localdb (отдельный сервис на хосте,
    # зеркалит данные пяти RIR — AFRINIC, APNIC, ARIN, LACNIC, RIPE NCC).
    # В v0.7 модуль ``src.rir_client`` определён, но нигде не используется
    # в UI/мониторинге. Применение — в v0.8 (DNS A/AAAA мониторинг с
    # ASN-фильтрацией для устранения шума от CDN round-robin).
    rir2localdb_enabled: bool = Field(
        True,
        description=(
            "Master kill-switch. False — rir_client возвращает RIRError"
            " без HTTP-запросов (для maintenance/тестов)."
        ),
    )
    rir2localdb_url: str = Field(
        "http://host.docker.internal:18000",
        description="Base URL rir2localdb без trailing slash. ADR 028-pattern.",
    )
    rir2localdb_timeout_seconds: float = Field(
        5.0,
        ge=1.0,
        le=30.0,
        description="Total request timeout. Cache hit ~100ms, miss ~500ms.",
    )
    rir2localdb_connect_timeout_seconds: float = Field(
        1.0,
        ge=0.5,
        le=5.0,
        description="Connect timeout (отдельно от read timeout).",
    )

    # ------------------------------------------------------------------
    # DNS monitoring (Этап 14, ADR 032)
    # ------------------------------------------------------------------
    # Async DNS resolver для DNS A/AAAA мониторинга с ASN-фильтрацией.
    # Используются external resolvers (Cloudflare + Google) как baseline
    # в v0.8.0. Локальный unbound — future work для v0.9.
    dns_resolvers: list[str] = Field(
        default_factory=lambda: ["1.1.1.1", "8.8.8.8"],
        description=(
            "External DNS resolvers. Используется как fallback chain "
            "(first → second). Если все не отвечают — DNSError(timeout)."
        ),
    )
    dns_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Per-query DNS timeout. Включает retries на одном сервере.",
    )
    dns_enabled: bool = Field(
        default=True,
        description=(
            "Master kill-switch. False → dns_monitor.resolve_records "
            "возвращает DNSError(disabled) без сетевых запросов."
        ),
    )

    # ------------------------------------------------------------------
    # Email / deep DNS resolver override (TASK-0079)
    # ------------------------------------------------------------------
    # Кастомные DNS nameservers для резолва MX/SPF/DMARC/DKIM + deep (MTA-STS etc).
    # Пустой список = системный resolver (поведение до TASK-0079, никаких регрессий).
    # Если в контейнере воркера системный DNS падает (Docker/ufw), оператор
    # ставит DNS_NAMESERVERS=1.1.1.1,8.8.8.8 (+ufw allow egress 53) — без правки кода.
    # Парсинг CSV как у admin_user_ids (NoDecode + before-validator).
    dns_nameservers: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "CSV-список DNS-серверов для email-intel/deep (MX/SPF/DMARC/DKIM + MTA-STS/DANE). "
            "Пусто = системный resolver (как раньше). Пример: 1.1.1.1,8.8.8.8"
        ),
    )

    @field_validator("dns_nameservers", mode="before")
    @classmethod
    def _parse_dns_nameservers(cls, value: object) -> object:
        """Разбирает строку '1.1.1.1,8.8.8.8' в список str (env обычно строка)."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    # ------------------------------------------------------------------
    # Backups (ADR 042, TASK-0058) — ежечасный pg_dump в scheduler
    # ------------------------------------------------------------------
    backup_dir: str = Field(
        "/backups",
        description="Directory where pg_dump writes backups (docker volume mount point).",
    )
    backup_keep: int = Field(
        36,
        ge=1,
        description="Number of most recent backup files to keep during rotation (by mtime).",
    )
    backup_min_bytes: int = Field(
        1024,
        ge=0,
        description="Minimum acceptable dump file size (bytes) for verify to pass.",
    )
    # Audit log retention (ADR 042, TASK-0061)
    # ------------------------------------------------------------------
    audit_retention_days: int = Field(
        90,
        ge=1,
        description="How many days to keep records in audit_log before cleanup (default 90 per ADR 042).",
    )

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def webapp_url(self) -> str:
        """Публичный URL Telegram WebApp (mini-app, ADR 043).

        Статика собирается в ``webapp/dist`` (vite ``base: '/app/'``) и
        отдаётся nginx из ``location /app/``. Единая точка вычисления —
        как ``webhook_url``.
        """
        return f"{self.webhook_base_url.rstrip('/')}/app/"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def instance_domain(self) -> str:
        """Извлекает домен из webhook_base_url для instance-тега (ADR 019, TASK-0019)."""
        # Парсим URL и берём только хост (без схемы и пути)
        from urllib.parse import urlparse

        parsed = urlparse(self.webhook_base_url)
        return parsed.netloc or ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает синглтон настроек.

    Кешируется на уровне процесса. Для тестов можно вызвать
    ``get_settings.cache_clear()``.
    """
    # обязательные поля берутся из env через pydantic-settings
    return Settings()
