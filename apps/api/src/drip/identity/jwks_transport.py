"""Isolated, capacity-limited JWKS transport. No application configuration imports."""

import json
import os
import re
import ssl
import subprocess
import sys
import time
from pathlib import Path
from threading import BoundedSemaphore, Thread
from typing import Any
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

MAX_JWKS_BYTES = 65536
_SLOTS = BoundedSemaphore(2)
_CLEANUP_SECONDS = 0.25
_ENDPOINT = re.compile(
    r"https://(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}/\.well-known/jwks\.json"
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _read_jwks(url: str, timeout: int) -> bytes:
    """Worker-only blocking I/O; the parent supplies the overall fetch deadline."""
    if not _ENDPOINT.fullmatch(url) or len(url) > 300:
        raise ValueError("Invalid signing key endpoint.")
    opener = build_opener(
        ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirect()
    )
    with opener.open(
        Request(url, headers={"Accept": "application/json"}), timeout=timeout
    ) as response:
        if (
            response.status != 200
            or response.headers.get("Content-Encoding", "identity") != "identity"
        ):
            raise ValueError("Invalid signing key response.")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdecimal() or int(length) > MAX_JWKS_BYTES):
            raise ValueError("Invalid signing key response.")
        body: bytes = response.read(MAX_JWKS_BYTES + 1)
        if len(body) > MAX_JWKS_BYTES or (length is not None and len(body) != int(length)):
            raise ValueError("Invalid signing key response.")
        return body


def _release(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdin, process.stdout):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass  # Child has exited; cleanup errors must not reveal transport details.
    _SLOTS.release()


def _reap(process: subprocess.Popen[bytes]) -> None:
    # Rare OS cleanup delay: retain capacity until the child really exits.
    try:
        process.wait()
    except OSError:
        return  # Unconfirmed exit: retain the slot, fail closed rather than overcommit.
    _release(process)


def fetch_jwks(url: str, timeout: int) -> bytes:
    """Fetch in a killable child, never an unbounded thread/connection queue.

    Deadline includes elapsed startup time, but OS process creation/termination
    cannot be given a hard real-time guarantee by Python. See the batch report.
    """
    if type(timeout) is not int or not 1 <= timeout <= 10 or not _ENDPOINT.fullmatch(url):
        raise ValueError("Invalid signing key transport configuration.")
    if not _SLOTS.acquire(blocking=False):
        raise ValueError("Signing key transport unavailable.")
    process: subprocess.Popen[bytes] | None = None
    deadline = time.monotonic() + timeout
    try:
        # No bearer token, application secrets or proxy credentials enter this child.
        environment = {
            name: os.environ[name] for name in ("SystemRoot", "WINDIR") if name in os.environ
        }
        process = subprocess.Popen(
            [sys.executable, "-I", str(Path(__file__).resolve()), "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        body, _ = process.communicate(json.dumps([url, timeout]).encode(), timeout=remaining)
        if time.monotonic() >= deadline or process.returncode != 0 or len(body) > MAX_JWKS_BYTES:
            raise ValueError("Signing key transport unavailable.")
        return body
    except Exception:
        raise ValueError("Signing key transport unavailable.") from None
    finally:
        if process is None:
            _SLOTS.release()
        else:
            try:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=_CLEANUP_SECONDS)
            except (OSError, subprocess.TimeoutExpired):
                # At most two reapers; no slot reuse while a worker could still connect.
                Thread(target=_reap, args=(process,), daemon=True).start()
            else:
                _release(process)


def _worker() -> int:
    try:
        request = sys.stdin.buffer.read(2049)
        if len(request) > 2048:
            return 1
        url, timeout = json.loads(request)
        if not isinstance(url, str) or type(timeout) is not int or not 1 <= timeout <= 10:
            return 1
        sys.stdout.buffer.write(_read_jwks(url, timeout))
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(_worker() if sys.argv[1:] == ["--worker"] else 1)
