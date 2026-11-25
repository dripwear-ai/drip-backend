"""Offline transport tests: mocked HTTP and local sleeping subprocesses only."""

import io
import json
import socket
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event
from unittest.mock import Mock

import pytest
from drip.identity import jwks_transport as transport

URL = "https://tenant.invalid/.well-known/jwks.json"


@pytest.fixture(autouse=True)
def offline_slots(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected network attempt")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(transport, "_SLOTS", BoundedSemaphore(2))


def fake_process():
    process = Mock(returncode=0, stdin=io.BytesIO(), stdout=io.BytesIO())
    process.communicate.return_value = (b'{"keys":[]}', None)
    process.poll.return_value = 0
    return process


def test_child_receives_only_public_configuration_and_no_proxy_secrets(monkeypatch):
    process = fake_process()
    factory = Mock(return_value=process)
    monkeypatch.setattr(transport.subprocess, "Popen", factory)
    monkeypatch.setenv("HTTPS_PROXY", "synthetic-private-proxy")
    monkeypatch.setenv("APPLICATION_SECRET", "synthetic-private-secret")
    assert transport.fetch_jwks(URL, 3) == b'{"keys":[]}'
    args, options = factory.call_args
    assert args[0][0] == sys.executable
    assert args[0][1] == "-I"
    assert args[0][-1] == "--worker"
    assert options["shell"] is False
    assert options["stderr"] == subprocess.DEVNULL
    assert set(options["env"]) <= {"SystemRoot", "WINDIR"}
    assert json.loads(process.communicate.call_args.args[0]) == [URL, 3]
    assert 0 < process.communicate.call_args.kwargs["timeout"] <= 3
    assert process.stdin.closed and process.stdout.closed
    assert transport._SLOTS.acquire(False) and transport._SLOTS.acquire(False)


@pytest.mark.parametrize(
    "failure",
    ["timeout", "read-error", "oversize", "exit-error", "late"],
    ids=["deadline", "read-error", "oversize", "exit-error", "late-output"],
)
def test_failed_or_late_response_is_redacted_and_releases_capacity(monkeypatch, caplog, failure):
    process = fake_process()
    if failure == "timeout":
        process.communicate.side_effect = subprocess.TimeoutExpired("synthetic-private-detail", 1)
        process.poll.return_value = None
    elif failure == "read-error":
        process.communicate.side_effect = OSError("synthetic-private-detail")
    elif failure == "oversize":
        process.communicate.return_value = (b"x" * (transport.MAX_JWKS_BYTES + 1), None)
    elif failure == "exit-error":
        process.returncode = 1
    else:
        monkeypatch.setattr(transport.time, "monotonic", Mock(side_effect=[0, 0.1, 3]))
    monkeypatch.setattr(transport.subprocess, "Popen", Mock(return_value=process))
    with pytest.raises(ValueError) as error:
        transport.fetch_jwks(URL, 3)
    assert str(error.value) == "Signing key transport unavailable."
    formatted = "".join(traceback.format_exception(error.value)) + caplog.text
    assert "synthetic-private-detail" not in formatted
    assert URL not in formatted
    if failure == "timeout":
        process.kill.assert_called_once()
    assert transport._SLOTS.acquire(False) and transport._SLOTS.acquire(False)


def test_startup_failure_does_not_poison_capacity(monkeypatch):
    factory = Mock(side_effect=OSError("synthetic-private-detail"))
    monkeypatch.setattr(transport.subprocess, "Popen", factory)
    for _ in range(4):
        with pytest.raises(ValueError, match="^Signing key transport unavailable.$"):
            transport.fetch_jwks(URL, 1)
    factory.side_effect = None
    factory.return_value = fake_process()
    assert transport.fetch_jwks(URL, 1) == b'{"keys":[]}'


def test_elapsed_startup_time_is_charged_to_deadline(monkeypatch):
    process = fake_process()
    process.poll.return_value = None
    monkeypatch.setattr(transport.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(transport.time, "monotonic", Mock(side_effect=[0, 2]))
    with pytest.raises(ValueError):
        transport.fetch_jwks(URL, 1)
    process.communicate.assert_not_called()
    process.kill.assert_called_once()


def test_two_active_helpers_bound_concurrency_without_queue(monkeypatch):
    entered = [Event(), Event()]
    release = Event()
    processes = [fake_process(), fake_process()]

    def delayed(index):
        def communicate(*args, **kwargs):
            entered[index].set()
            assert release.wait(5)
            return b'{"keys":[]}', None

        return communicate

    for index, process in enumerate(processes):
        process.communicate.side_effect = delayed(index)
    factory = Mock(side_effect=processes)
    monkeypatch.setattr(transport.subprocess, "Popen", factory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(transport.fetch_jwks, URL, 10) for _ in range(2)]
        try:
            assert all(event.wait(3) for event in entered)
            for _ in range(30):
                with pytest.raises(ValueError, match="^Signing key transport unavailable.$"):
                    transport.fetch_jwks(URL, 1)
            assert factory.call_count == 2
        finally:
            release.set()
        assert all(future.result(timeout=3) == b'{"keys":[]}' for future in futures)


def test_unconfirmed_child_exit_keeps_capacity_reserved(monkeypatch):
    process = fake_process()
    process.poll.return_value = None
    process.communicate.side_effect = subprocess.TimeoutExpired("worker", 1)
    process.wait.side_effect = subprocess.TimeoutExpired("worker", 0.25)
    monkeypatch.setattr(transport.subprocess, "Popen", Mock(return_value=process))
    reaper = Mock()
    monkeypatch.setattr(transport, "Thread", reaper)
    for _ in range(2):
        with pytest.raises(ValueError):
            transport.fetch_jwks(URL, 1)
    assert not transport._SLOTS.acquire(False)
    assert reaper.call_count == 2
    assert reaper.call_args.kwargs["daemon"] is True
    process.wait.side_effect = None
    transport._reap(process)
    assert transport._SLOTS.acquire(False)


def test_real_sleeping_worker_is_killed_without_network(monkeypatch):
    actual_popen = subprocess.Popen
    children = []

    def sleeping_worker(command, **kwargs):
        # Exercise real process timeout/kill, not HTTP/DNS or a real provider.
        child = actual_popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(transport.subprocess, "Popen", sleeping_worker)
    try:
        with pytest.raises(ValueError, match="^Signing key transport unavailable.$"):
            transport.fetch_jwks(URL, 1)
        assert len(children) == 1
        assert children[0].poll() is not None
        assert transport._SLOTS.acquire(False) and transport._SLOTS.acquire(False)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


@pytest.mark.parametrize(
    "headers,body",
    [
        ({"Content-Length": "20"}, b"short"),
        ({"Content-Length": "1"}, b"long"),
        ({"Content-Length": "invalid"}, b""),
        ({"Content-Length": "65537"}, b""),
        ({"Content-Encoding": "gzip"}, b""),
    ],
    ids=["incomplete", "excess", "invalid-length", "oversize-length", "compressed"],
)
def test_worker_rejects_incomplete_or_unbounded_responses(monkeypatch, headers, body):
    response = Mock(status=200, headers=headers)
    response.read.return_value = body
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(transport, "build_opener", Mock(return_value=opener))
    with pytest.raises(ValueError):
        transport._read_jwks(URL, 1)


@pytest.mark.parametrize(
    "url",
    [
        "http://tenant.invalid/.well-known/jwks.json",
        "https://user@tenant.invalid/.well-known/jwks.json",
        URL + "?redirect=other",
        URL + "#fragment",
        "https://127.0.0.1/.well-known/jwks.json",
    ],
    ids=["http", "userinfo", "query", "fragment", "ip"],
)
def test_invalid_destination_cannot_create_worker(monkeypatch, url):
    factory = Mock()
    monkeypatch.setattr(transport.subprocess, "Popen", factory)
    with pytest.raises(ValueError, match="^Invalid signing key transport configuration.$"):
        transport.fetch_jwks(url, 1)
    factory.assert_not_called()
