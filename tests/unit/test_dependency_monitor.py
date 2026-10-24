"""Regression checks for the standalone operations monitor (no Docker required)."""

import asyncio
import io
from unittest.mock import create_autospec, patch

import pytest

from scripts.ops.dependency_monitor import collect, http_probe, next_alert, whois_probe


def test_partial_failure_alerts_immediately_and_deduplicates() -> None:
    state = {}
    issues = {"ru_relay": "2/4 successful"}
    assert next_alert(state, issues, 100, 1800) == "failure"
    # Failed delivery must not suppress the next attempt.
    assert next_alert(state, issues, 101, 1800) == "failure"
    state.update(notified_issues=["ru_relay"], last_alert=101)
    assert next_alert(state, {"ru_relay": "1/4 successful"}, 102, 1800) is None
    assert next_alert(state, issues, 1901, 1800) == "failure"


def test_recovery_requires_two_clean_runs_and_is_not_sent_on_healthy_start() -> None:
    state = {}
    assert next_alert(state, {}, 100, 1800) is None
    state.update(notified_issues=["ru_relay"], last_alert=100)
    assert next_alert(state, {}, 101, 1800) is None
    assert next_alert(state, {"ru_relay": "failed"}, 102, 1800) is None
    assert next_alert(state, {}, 103, 1800) is None
    assert next_alert(state, {}, 104, 1800) == "recovery"


def test_new_failed_component_notifies_without_waiting_for_reminder() -> None:
    state = {"notified_issues": ["ru_relay"], "last_alert": 100}
    assert next_alert(state, {"ru_relay": "failed", "bot_health": "failed"}, 101, 1800)


@pytest.mark.asyncio
async def test_whois_probe_handles_split_tcp_response_and_rejects_no_data() -> None:
    responses = [b"state: REG", b"ISTERED, DELEGATED\r\n"]
    finished = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        assert await reader.readline() == b"yandex.ru\r\n"
        for part in responses:
            writer.write(part)
            await writer.drain()
            await asyncio.sleep(0.01)
        writer.close()
        await writer.wait_closed()
        finished.set()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        assert await whois_probe("127.0.0.1", port, "yandex.ru", 1)
        await asyncio.wait_for(finished.wait(), timeout=1)
        finished.clear()
        responses[:] = [b"No entries found for the selected source(s).\r\n"]
        assert not await whois_probe("127.0.0.1", port, "yandex.ru", 1)
        await asyncio.wait_for(finished.wait(), timeout=1)


@pytest.mark.asyncio
async def test_whois_probe_times_out_without_registered_response() -> None:
    finished = asyncio.Event()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read()
        writer.close()
        await writer.wait_closed()
        finished.set()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        assert not await whois_probe("127.0.0.1", port, "yandex.ru", 0.05)
        await asyncio.wait_for(finished.wait(), timeout=1)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ('{"ok": false, "error": "no_data"}', False),
        ('{"ok": true, "source": "whois_ru_upstream", "data": "No entries"}', False),
        (
            '{"ok": true, "source": "whois_ru_upstream", "data": "state: REGISTERED"}',
            True,
        ),
    ],
)
def test_http_200_is_not_enough_for_lookup_health(payload: str, expected: bool) -> None:
    # A real stream exercises JSON decoding, rather than mocking parsed fields.
    response = io.BytesIO(payload.encode())
    response.status = 200
    with patch("urllib.request.urlopen", autospec=True, return_value=response):
        assert http_probe("http://proxy/q/yandex.ru", proxy=True) is expected


@pytest.mark.asyncio
async def test_healthy_http_and_container_cannot_mask_partial_relay_failure() -> None:
    from scripts.ops.dependency_monitor import command

    with (
        patch(
            "scripts.ops.dependency_monitor.whois_probe",
            autospec=True,
            side_effect=[True, False, True, False],
        ),
        patch(
            "scripts.ops.dependency_monitor.http_probe",
            new=create_autospec(http_probe, return_value=True),
        ),
        patch(
            "scripts.ops.dependency_monitor.command",
            new=create_autospec(command, return_value=b"[]"),
        ),
    ):
        issues, measurements = await collect({})
    assert list(issues) == ["ru_relay"]
    assert measurements["relay_successes"] == 2
