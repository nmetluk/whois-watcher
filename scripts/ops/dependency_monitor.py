"""Host-level checks, independent of ARQ; Telegram delivery uses the app's aiogram.

Only Python's standard library is needed on the host. No credentials or WHOIS
responses are copied out of containers. systemd serializes runs of this service.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import time
import urllib.request
from contextlib import suppress
from pathlib import Path
from typing import Any

LOG = logging.getLogger("ww.dependencies")
REGISTERED = re.compile(rb"^state:\s*REGISTERED\b", re.MULTILINE | re.IGNORECASE)

# Exceptions deliberately expose only their type, never Bot tokens or responses.
DELIVER = """
import asyncio, json, sys
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from src.config.settings import get_settings
async def main():
    settings = get_settings()
    if settings.admin_channel_id is None:
        raise RuntimeError('admin_channel_id is not configured')
    text = json.load(sys.stdin)['text']
    async with Bot(token=settings.bot_token.get_secret_value(),
                   session=AiohttpSession(timeout=8)) as bot:
        message = await bot.send_message(
            chat_id=settings.admin_channel_id, text=text, parse_mode=None)
        print(json.dumps({'delivered': True, 'message_id': message.message_id}))
try:
    asyncio.run(main())
except Exception as exc:
    print(json.dumps({'delivered': False, 'error_type': type(exc).__name__}))
    sys.exit(1)
"""


async def command(*args: str, data: bytes | None = None, timeout: float = 15) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if data is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(data), timeout)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise
    if process.returncode:
        raise RuntimeError(f"command failed: {args[0]}")
    return stdout


async def whois_probe(host: str, port: int, domain: str, timeout: float) -> bool:
    writer: asyncio.StreamWriter | None = None
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(domain.encode("ascii") + b"\r\n")
            await writer.drain()
            # Read until EOF: TCP can split 'state: REGISTERED' across packets.
            response = await reader.read(65536)
            while response and len(response) < 65536 and not REGISTERED.search(response):
                chunk = await reader.read(65536 - len(response))
                if not chunk:
                    break
                response += chunk
            return bool(REGISTERED.search(response))
    except (OSError, TimeoutError):
        return False
    finally:
        if writer is not None:
            writer.close()
            with suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), timeout=1)


def http_probe(url: str, proxy: bool = False) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                return False
            if not proxy:
                return True
            payload = json.load(response)
        return (
            payload.get("ok") is True
            and payload.get("source") == "whois_ru_upstream"
            and isinstance(payload.get("data"), str)
            and bool(REGISTERED.search(payload["data"].encode("utf-8")))
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


async def collect(config: dict[str, Any]) -> tuple[dict[str, str], dict[str, object]]:
    issues: dict[str, str] = {}
    probes = int(config.get("samples", 4))
    results = await asyncio.gather(
        *(
            whois_probe(
                config.get("relay_host", "127.0.0.1"),
                int(config.get("relay_port", 10443)),
                config.get("sentinel", "yandex.ru"),
                float(config.get("probe_timeout", 4)),
            )
            for _ in range(probes)
        )
    )
    successes = sum(results)
    if successes < probes:
        issues["ru_relay"] = f"RU WHOIS: {successes}/{probes} successful real queries"
    urls = {
        "bot_health": config.get("bot_health_url", "http://127.0.0.1:8091/health"),
        "proxy_health": config.get("proxy_health_url", "http://127.0.0.1:8043/healthz"),
        "proxy_lookup": config.get("proxy_lookup_url", "http://127.0.0.1:8043/q/yandex.ru"),
    }
    # The proxy can take 15s to fail its upstream. The independent relay probe
    # already detects this; fail the HTTP lookup on a bounded 5s timeout.
    checks = await asyncio.gather(
        *(asyncio.to_thread(http_probe, url, name == "proxy_lookup") for name, url in urls.items())
    )
    for name, ok in zip(urls, checks, strict=True):
        if not ok:
            issues[name] = f"{name}: failed"
    names = config.get(
        "containers", ["ww-bot", "ww-worker", "ww-scheduler", "ww-postgres", "ww-redis"]
    )
    try:
        raw = await command("docker", "inspect", *names)
        for container in json.loads(raw):
            name = container["Name"].lstrip("/")
            state = container["State"]
            if not state.get("Running") or state.get("Health", {}).get("Status") == "unhealthy":
                issues[f"container:{name}"] = f"{name}: stopped or unhealthy"
    except (OSError, RuntimeError, TimeoutError, ValueError, KeyError):
        issues["docker"] = "Cannot inspect expected containers"
    return issues, {"relay_successes": successes, "relay_samples": probes}


def next_alert(
    state: dict[str, Any], issues: dict[str, str], now: float, reminder_seconds: int
) -> str | None:
    """Do not mark notification delivered until Telegram confirms the message."""
    previous = state.get("notified_issues", [])
    current = sorted(issues)
    if current:
        state["healthy_runs"] = 0
        if current != previous or now - state.get("last_alert", 0) >= reminder_seconds:
            return "failure"
    elif previous:
        state["healthy_runs"] = state.get("healthy_runs", 0) + 1
        if state["healthy_runs"] >= 2:
            return "recovery"
    else:
        state["healthy_runs"] = 0
    return None


async def deliver(config: dict[str, Any], text: str) -> bool:
    data = json.dumps({"text": text}).encode()
    for container in config.get("send_containers", ["ww-worker", "ww-bot", "ww-scheduler"]):
        try:
            raw = await command(
                "docker", "exec", "-i", container, "python", "-c", DELIVER, data=data
            )
            receipt = json.loads(raw)
            if receipt.get("delivered") is True:
                LOG.info("admin alert delivered: message_id=%s", receipt.get("message_id"))
                return True
        except (OSError, RuntimeError, TimeoutError, ValueError):
            LOG.warning("admin delivery via %s failed", container)
    LOG.error("admin delivery failed; notification remains pending for the next run")
    return False


async def run(config: dict[str, Any], check_only: bool, self_test: bool) -> int:
    state_path = Path(config.get("state_path", "/var/lib/ww-dependency-monitor/state.json"))
    if self_test:
        state_path = state_path.with_name("self-test.json")
        # Separate state, real delivery, no changes to live dependencies.
        state_path.unlink(missing_ok=True)
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            LOG.warning("Cannot read previous notification state; starting fresh")
    issues, measurements = await collect(config)
    LOG.info("checks: %s", json.dumps({"issues": issues, **measurements}, sort_keys=True))
    if check_only:
        return int(bool(issues))
    scenarios = [{"self_test": "Deliberate alert-path self-test; production is unchanged"}, {}, {}]
    for current in scenarios if self_test else [issues]:
        now = time.time()
        kind = next_alert(state, current, now, int(config.get("reminder_seconds", 1800)))
        if kind:
            prefix = "[SELF-TEST] " if self_test else ""
            label = config.get("label", "Whois Watcher dependencies")
            body = "\n".join(current.values()) if current else "All dependency checks recovered."
            severity = "#critical" if kind == "failure" else "#info"
            text = f"{severity}\n{prefix}{label}: {kind}\n\n{body}"
            if await deliver(config, text):
                state["notified_issues"] = sorted(current)
                state["last_alert"] = now
            else:
                return 1
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.replace(state_path)
    return int(bool(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = json.loads(args.config.read_text())
    if not 1 <= int(config.get("samples", 4)) <= 8:
        parser.error("samples must be between 1 and 8")
    return asyncio.run(run(config, args.check_only, args.self_test))


if __name__ == "__main__":
    raise SystemExit(main())
