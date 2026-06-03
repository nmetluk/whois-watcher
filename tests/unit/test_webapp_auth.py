"""Unit tests for WebApp initData validator (TASK-0066).

Uses the exact algorithm. Includes:
- self-signed valid vector (roundtrip)
- forged hash → mismatch
- expired auth_date → 401 path
- malformed → errors
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote

import pytest

from src.bot.webapp.auth import (
    WebAppAuthResult,
    validate_init_data,
)


def _sign_init_data(data_check_string: str, bot_token: str) -> str:
    """Helper: produce correct hash for a data_check_string (mimics Telegram)."""
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()


def _build_init_data(pairs: dict[str, str], bot_token: str) -> str:
    """Build a valid initData string + correct hash for given pairs (no 'hash' in pairs)."""
    # Note: Telegram side puts encoded values; we simulate by quoting where needed.
    items = []
    for k in sorted(pairs):
        v = pairs[k]
        # values that are JSON or complex are already "encoded" in real, here we quote for the wire
        items.append(f"{k}={quote(v, safe='')}")
    data_str = "&".join(items)
    # now compute check string using UNQUOTED values (as validator does)
    unq = dict(pairs)
    dcs = "\n".join(f"{k}={unq[k]}" for k in sorted(unq))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return f"{data_str}&hash={h}"


BOT_TOKEN = "123456:ABCDEF-ghIklzyx57W2v1u123ew11-test-token-for-webapp"


def test_validate_valid_roundtrip():
    now = int(time.time())
    user_json = '{"id":123456789,"first_name":"Test","username":"tester","language_code":"ru"}'
    pairs = {
        "auth_date": str(now - 10),
        "query_id": "test123",
        "user": user_json,
    }
    init = _build_init_data(pairs, BOT_TOKEN)
    res = validate_init_data(init, BOT_TOKEN, ttl_seconds=3600)
    assert isinstance(res, WebAppAuthResult)
    assert res.telegram_id == 123456789
    assert res.username == "tester"
    assert res.auth_date == now - 10


def test_validate_bad_signature():
    now = int(time.time())
    user_json = '{"id":123456789}'
    pairs = {"auth_date": str(now - 5), "user": user_json}
    init = _build_init_data(pairs, BOT_TOKEN)
    # tamper hash
    init_bad = init.replace("hash=", "hash=deadbeef")
    with pytest.raises(ValueError, match="signature mismatch"):
        validate_init_data(init_bad, BOT_TOKEN, 3600)


def test_validate_expired():
    old = int(time.time()) - 100000
    user_json = '{"id":42}'
    pairs = {"auth_date": str(old), "user": user_json}
    init = _build_init_data(pairs, BOT_TOKEN)
    with pytest.raises(ValueError, match="expired"):
        validate_init_data(init, BOT_TOKEN, ttl_seconds=60)


def test_validate_missing_fields():
    with pytest.raises(ValueError):
        validate_init_data("", BOT_TOKEN, 3600)
    with pytest.raises(ValueError, match="hash"):
        validate_init_data("user=%7B%7D&auth_date=1", BOT_TOKEN, 3600)
    with pytest.raises(ValueError, match="user"):
        validate_init_data("hash=abc&auth_date=1", BOT_TOKEN, 3600)


def test_validate_bad_user_json():
    now = int(time.time())
    pairs = {"auth_date": str(now), "user": "not-json"}
    init = _build_init_data(pairs, BOT_TOKEN)
    with pytest.raises(ValueError, match="bad user"):
        validate_init_data(init, BOT_TOKEN, 3600)
