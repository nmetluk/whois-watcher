"""Telegram WebApp initData validation (exact algorithm per Telegram docs + TASK-0066).

Clean functions for unit-testing (no side effects, no HTTP).
Auth middleware for aiohttp: extracts initData from headers (X-*/Authorization tma), validates,
loads/creates User, attaches to request['user'].
Invalid/expired → 401 JSON.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

from aiohttp import web

from src.config.settings import Settings
from src.db.repositories.users import UserRepository
from src.db.session import get_session

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class WebAppAuthResult:
    """Parsed result of successful initData validation."""

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    auth_date: int = 0
    query_id: str | None = None


def validate_init_data(init_data: str | None, bot_token: str, ttl_seconds: int) -> WebAppAuthResult:
    """Validate initData signature and freshness (precise Telegram algorithm).

    Steps (do not reorder key/msg):
    1. Parse querystring pairs; drop `hash`.
    2. data_check_string = sorted(key=value, key asc) joined by '\\n' (values unquoted).
    3. secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
    4. calc = hex( HMAC_SHA256(key=secret_key, msg=data_check_string) )
    5. compare_digest(calc, received_hash)
    6. auth_date freshness: now - auth_date <= ttl

    Raises ValueError(msg) on any failure — for tests and middleware.
    """
    if not init_data:
        raise ValueError("init_data is empty")
    if not bot_token:
        raise ValueError("bot_token is empty")

    pairs: dict[str, str] = {}
    received_hash: str | None = None

    for chunk in init_data.split("&"):
        if not chunk or "=" not in chunk:
            continue
        k, _, v = chunk.partition("=")
        if k == "hash":
            received_hash = v
            continue
        # Values in data_check_string must be unquoted (standard for this check)
        pairs[k] = unquote(v)

    if received_hash is None:
        raise ValueError("missing hash")
    if "user" not in pairs:
        raise ValueError("missing user field")

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))

    # Critical order: key="WebAppData", msg=bot_token (never swap!)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("signature mismatch")

    # Freshness (replay protection)
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except (ValueError, TypeError):
        raise ValueError("bad auth_date") from None
    now_ts = int(datetime.now(UTC).timestamp())
    if now_ts - auth_date > ttl_seconds:
        raise ValueError("initData expired (replay)")

    # Parse user object (required)
    try:
        user_obj: dict[str, Any] = json.loads(pairs["user"])
        tg_id: int = int(user_obj["id"])
    except Exception as exc:
        raise ValueError(f"bad user payload: {exc}") from exc

    return WebAppAuthResult(
        telegram_id=tg_id,
        username=user_obj.get("username"),
        first_name=user_obj.get("first_name"),
        last_name=user_obj.get("last_name"),
        auth_date=auth_date,
        query_id=pairs.get("query_id"),
    )


def _extract_init_data(request: web.Request, *, allow_dev_fallback: bool = False) -> str | None:
    """Extract raw initData string from common headers used by Telegram WebApps.

    Priority:
    - X-Telegram-Init-Data / X-Init-Data / X-Telegram-Web-App-Init-Data
    - Authorization: tma <data>  (or TMA)
    - Fallback (dev only, gated): query param initData=...
    """
    for h in ("X-Telegram-Init-Data", "X-Init-Data", "X-Telegram-Web-App-Init-Data"):
        val = request.headers.get(h)
        if val:
            return val.strip()

    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth:
        # Accept "tma <data>" or "TMA <data>"
        parts = auth.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "tma":
            return parts[1].strip()

    # Dev convenience ONLY if explicitly allowed (env=development). Never in prod.
    if allow_dev_fallback:
        q = request.query.get("initData") or request.query.get("_initData")
        if q:
            return q.strip()

    return None


def create_webapp_auth_middleware(settings: Settings) -> Any:
    """Factory: returns aiohttp middleware that does initData auth + user load/register.

    On success: request['user'] = User (db model), request['webapp_auth'] = WebAppAuthResult
    On failure: 401 JSON, no further processing.
    """

    @web.middleware
    async def _auth_mw(request: web.Request, handler: Any) -> Any:
        # Preflight must pass before auth (F5): OPTIONS has no initData, cors_mw will answer 204.
        if request.method == "OPTIONS":
            return await handler(request)
        is_dev = getattr(settings, "environment", "production") == "development"
        init_data = _extract_init_data(request, allow_dev_fallback=is_dev)
        try:
            bot_token = settings.bot_token.get_secret_value()
            ttl = settings.webapp_initdata_ttl
            auth_res = validate_init_data(init_data, bot_token, ttl)
        except ValueError as exc:
            logger.debug("webapp auth failed: %s", exc)
            return web.json_response({"error": "unauthorized", "reason": str(exc)}, status=401)
        except Exception:
            logger.exception("webapp auth unexpected error")
            return web.json_response({"error": "unauthorized"}, status=401)

        # Load or auto-create user (like UserRegisterMiddleware for bot), touch active
        try:
            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get_by_telegram_id(auth_res.telegram_id)
                if user is None:
                    user = await repo.create(
                        telegram_id=auth_res.telegram_id,
                        username=auth_res.username,
                        # defaults from settings (language etc) are applied in create
                    )
                else:
                    await repo.touch_last_active(user.id)
                request["user"] = user
                request["webapp_auth"] = auth_res
        except Exception:
            logger.exception("webapp auth: failed to load/create user")
            return web.json_response({"error": "unauthorized"}, status=401)

        return await handler(request)

    return _auth_mw


# For tests / direct use without HTTP
__all__ = [
    "WebAppAuthResult",
    "validate_init_data",
    "create_webapp_auth_middleware",
]
