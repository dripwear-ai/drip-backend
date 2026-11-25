"""Offline regressions for canonical targets and the real pytest startup boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.disposable_targets import (
    POSTGRES_URL,
    REDIS_URL,
    UnsafeTestTarget,
    prepare_test_environment,
    validate_disposable_targets,
)

API_ROOT = Path(__file__).resolve().parents[1]
PG_KEY = "DRIP_TEST_DATABASE_URL"
REDIS_KEY = "DRIP_TEST_REDIS_URL"


def documented_environment():
    return {PG_KEY: POSTGRES_URL, REDIS_KEY: REDIS_URL}


def invalid_variants(url):
    """Named cases keep synthetic URL/credential values out of pytest node IDs."""
    scheme, rest = url.split("://", 1)
    authority, database = rest.split("/", 1)
    hostport = authority.split("@")[-1]
    host, port = hostport.split(":")
    cases = {
        "empty": "",
        "garbage": "not-a-url",
        "scheme-missing": "//" + rest,
        "scheme-case": scheme.upper() + "://" + rest,
        "scheme-alternate": "https://" + rest,
        "scheme-extra-driver": scheme + "+other://" + rest,
        "scheme-one-slash": scheme + ":/" + rest,
        "scheme-three-slashes": scheme + ":///" + rest,
        "host-localhost": url.replace(host, "localhost"),
        "host-remote": url.replace(host, "unrelated.example.invalid"),
        "host-short-ip": url.replace(host, "127.1"),
        "host-integer": url.replace(host, "2130706433"),
        "host-hex": url.replace(host, "0x7f000001"),
        "host-octal": url.replace(host, "0177.0.0.1"),
        "host-other-loopback": url.replace(host, "127.0.0.2"),
        "host-ipv6": url.replace(host, "[::1]"),
        "host-ipv6-mapped": url.replace(host, "[::ffff:127.0.0.1]"),
        "host-bracket-malformed": url.replace(host, "[127.0.0.1"),
        "host-trailing-dot": url.replace(host, host + "."),
        "host-suffix": url.replace(host, host + ".unrelated.invalid"),
        "host-encoded": url.replace(host, "%31%32%37.0.0.1"),
        "host-unicode": url.replace(host, "１２７.0.0.1"),
        "port-missing": url.replace(":" + port, ""),
        "port-empty": url.replace(port, ""),
        "port-other": url.replace(port, "5435"),
        "port-leading-zero": url.replace(port, "0" + port),
        "port-plus": url.replace(port, "+" + port),
        "port-encoded": url.replace(port, "%35" + port[1:]),
        "port-range": url.replace(port, "65536"),
        "port-nonnumeric": url.replace(port, "port"),
        "database-missing": scheme + "://" + authority,
        "database-empty": scheme + "://" + authority + "/",
        "database-other": scheme + "://" + authority + "/unrelated",
        "database-encoded": scheme + "://" + authority + "/%" + format(ord(database[0]), "02x") + database[1:],
        "database-double-encoded": scheme + "://" + authority + "/%25" + format(ord(database[0]), "02x") + database[1:],
        "database-double-slash": scheme + "://" + authority + "//" + database,
        "database-trailing-slash": url + "/",
        "database-dot-segment": scheme + "://" + authority + "/other/../" + database,
        "database-encoded-slash": url + "%2fother",
        "query-empty": url + "?",
        "query-host-override": url + "?host=unrelated.invalid",
        "query-port-override": url + "?port=5435",
        "query-database-override": url + "?db=1&database=unrelated",
        "query-repeated": url + "?host=127.0.0.1&host=unrelated.invalid",
        "query-unix-socket": url + "?host=%2Ftmp%2Funrelated",
        "fragment-empty": url + "#",
        "fragment-secret": url + "#never-log-this",
        "userinfo-extra-at": scheme + "://never-log-this@" + rest,
        "userinfo-host-disguise": scheme + "://" + authority + "@unrelated.invalid/" + database,
        "userinfo-encoded-at": scheme + "://never%40log:this@" + rest,
        "authority-backslash": scheme + "://" + authority + "\\@unrelated.invalid/" + database,
        "authority-multiple-hosts": scheme + "://" + authority + ",unrelated.invalid/" + database,
        "leading-space": " " + url,
        "trailing-space": url + " ",
        "leading-control": "\x00" + url,
        "embedded-tab": url.replace(host, "127.\t0.0.1"),
        "embedded-newline": url.replace(host, "127.\n0.0.1"),
        "trailing-newline": url + "\n",
        "backslashes": url.replace("/", "\\"),
    }
    return cases


BAD_CASES = [
    pytest.param(key, value, id=label + "-" + name)
    for key, url, label in [(PG_KEY, POSTGRES_URL, "postgres"), (REDIS_KEY, REDIS_URL, "redis")]
    for name, value in invalid_variants(url).items()
] + [
    pytest.param(PG_KEY, POSTGRES_URL.replace("postgresql+asyncpg", "postgresql"), id="postgres-sync-scheme"),
    pytest.param(PG_KEY, POSTGRES_URL.replace("drip_test:disposable_test_only@", ""), id="postgres-missing-userinfo"),
    pytest.param(PG_KEY, POSTGRES_URL.replace("disposable_test_only", "never-log-this"), id="postgres-other-credential"),
    pytest.param(PG_KEY, POSTGRES_URL.replace("drip_test", "drip%5Ftest"), id="postgres-encoded-user"),
    pytest.param(REDIS_KEY, REDIS_URL.replace("redis:", "rediss:"), id="redis-tls-scheme"),
    pytest.param(REDIS_KEY, REDIS_URL.replace("redis:", "unix:"), id="redis-unix-scheme"),
    pytest.param(REDIS_KEY, REDIS_URL.replace("//", "//:never-log-this@"), id="redis-userinfo"),
    *[pytest.param(REDIS_KEY, REDIS_URL[:-1] + value, id="redis-db-" + name) for name, value in [
        ("one", "1"), ("negative", "-1"), ("zero-padded", "00"), ("plus", "+0"),
        ("decimal", "0.0"), ("extra", "0/1"), ("params", "0;db=1"),
    ]],
]


def test_accepts_both_documented_targets():
    assert validate_disposable_targets(documented_environment()) == (POSTGRES_URL, REDIS_URL)


ALIAS_CASES = [
    pytest.param({PG_KEY.lower(): POSTGRES_URL}, id="postgres-lowercase"),
    pytest.param({"Drip_Test_Database_Url": POSTGRES_URL}, id="postgres-mixed-case"),
    pytest.param({REDIS_KEY.lower(): REDIS_URL}, id="redis-lowercase"),
    pytest.param({"Drip_Test_Redis_Url": REDIS_URL}, id="redis-mixed-case"),
    pytest.param({PG_KEY.lower(): ""}, id="postgres-empty-alias"),
    pytest.param({REDIS_KEY.lower(): ""}, id="redis-empty-alias"),
    pytest.param({PG_KEY.lower(): "never-log-this"}, id="postgres-malformed-alias"),
    pytest.param({REDIS_KEY.lower(): "never-log-this"}, id="redis-malformed-alias"),
    pytest.param(documented_environment() | {PG_KEY.lower(): POSTGRES_URL}, id="postgres-alias-with-valid-exact"),
    pytest.param(documented_environment() | {REDIS_KEY.lower(): REDIS_URL}, id="redis-alias-with-valid-exact"),
    pytest.param(documented_environment() | {PG_KEY: "never-log-this", PG_KEY.lower(): POSTGRES_URL}, id="postgres-alias-with-invalid-exact"),
    pytest.param(documented_environment() | {REDIS_KEY: "never-log-this", REDIS_KEY.lower(): REDIS_URL}, id="redis-alias-with-invalid-exact"),
    pytest.param({PG_KEY.lower(): POSTGRES_URL, "Drip_Test_Redis_Url": REDIS_URL}, id="both-aliases"),
]


@pytest.mark.parametrize("markexpr", ["integration", "not integration"])
@pytest.mark.parametrize("targets", ALIAS_CASES)
def test_aliases_fail_redacted_without_environment_mutation(targets, markexpr):
    environment = targets | {
        "DATABASE_URL": "untouched", "redis_url": "untouched",
        "environment": "production", "drip_env_file": "untouched.env",
    }
    before = environment.copy()
    with pytest.raises(UnsafeTestTarget) as exc:
        prepare_test_environment(environment, markexpr)
    assert str(exc.value) == "Test-target variables must use only the documented uppercase names."
    assert environment == before


@pytest.mark.parametrize("markexpr", ["integration", "not integration"])
def test_exact_uppercase_targets_still_prepare_successfully(markexpr):
    environment = documented_environment()
    prepare_test_environment(environment, markexpr)
    assert environment == documented_environment() | {
        "ENVIRONMENT": "test", "DRIP_ENV_FILE": "",
        "DATABASE_URL": POSTGRES_URL, "REDIS_URL": REDIS_URL,
    }


@pytest.mark.parametrize("key,value", BAD_CASES)
def test_rejects_noncanonical_target_independently_without_echoing_it(key, value):
    environment = documented_environment()
    environment[key] = value
    with pytest.raises(UnsafeTestTarget) as exc:
        validate_disposable_targets(environment)
    service = "PostgreSQL" if key == PG_KEY else "Redis"
    assert str(exc.value) == f"{key} must be the documented disposable {service} URL."
    assert "never-log-this" not in str(exc.value)
    assert "://" not in str(exc.value)


@pytest.mark.parametrize("missing", [(PG_KEY,), (REDIS_KEY,), (PG_KEY, REDIS_KEY)])
def test_missing_target_is_rejected(missing):
    environment = documented_environment()
    for key in missing:
        del environment[key]
    with pytest.raises(UnsafeTestTarget):
        validate_disposable_targets(environment)


@pytest.mark.parametrize("markexpr", ["integration", "", "not integration or integration", "not integration and other"])
def test_live_or_unrecognized_selection_never_infers_explicit_targets(markexpr):
    with pytest.raises(UnsafeTestTarget):
        prepare_test_environment({}, markexpr)


@pytest.mark.parametrize("markexpr", ["integration", "not integration"])
def test_failure_does_not_partially_mutate_environment(markexpr):
    environment = documented_environment() | {REDIS_KEY: "", "DATABASE_URL": "untouched"}
    before = environment.copy()
    with pytest.raises(UnsafeTestTarget):
        prepare_test_environment(environment, markexpr)
    assert environment == before


def test_nonlive_defaults_are_disposable_and_cannot_authorize_live_tests():
    environment = {"DATABASE_URL": "unrelated", "redis_url": "unrelated", "UNRELATED": "keep"}
    prepare_test_environment(environment, "not integration")
    assert environment == {
        "ENVIRONMENT": "test", "DRIP_ENV_FILE": "", "DATABASE_URL": POSTGRES_URL,
        "REDIS_URL": REDIS_URL, "UNRELATED": "keep",
    }
    with pytest.raises(UnsafeTestTarget):
        validate_disposable_targets(environment)


def test_effective_settings_cannot_use_inherited_case_aliases(monkeypatch):
    from drip.core.config import Settings

    environment = documented_environment() | {
        "DATABASE_URL": "unrelated", "database_url": "unrelated",
        "REDIS_URL": "unrelated", "redis_url": "unrelated",
        "environment": "production", "drip_env_file": "unrelated.env",
    }
    prepare_test_environment(environment, "integration")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    settings = Settings()
    assert settings.DATABASE_URL == POSTGRES_URL
    assert settings.REDIS_URL == REDIS_URL


# A fresh interpreter exercises the actual conftest hook before collection. Spies
# fail on engine, pool, client, DNS or socket access; no live service is needed.
STARTUP_PROBE = r'''
import json
import os
import socket
import sys
from unittest.mock import patch

import asyncpg
import pytest
import redis
import redis.asyncio as aioredis
import sqlalchemy
import sqlalchemy.ext.asyncio as sa_async
from sqlalchemy.pool import Pool

payload = json.loads(sys.stdin.read())
if any(name != name.upper() for name in payload["environment"]):
    # Windows os.environ uppercases keys. Preserve aliases in a mapping double
    # while exercising the real conftest hook and the same infrastructure spies.
    patch.object(os, "environ", dict(os.environ) | payload["environment"]).start()
else:
    os.environ.update(payload["environment"])
calls = []
def forbidden(name):
    def spy(*args, **kwargs):
        calls.append(name)
        raise AssertionError("Infrastructure creation attempted")
    return spy

targets = [
    (sa_async, "create_async_engine"), (sqlalchemy, "create_engine"),
    (Pool, "__init__"), (asyncpg, "connect"), (asyncpg, "create_pool"),
    (redis, "from_url"), (aioredis, "from_url"),
    (redis.Redis, "__init__"), (aioredis.Redis, "__init__"),
    (redis.ConnectionPool, "__init__"), (aioredis.ConnectionPool, "__init__"),
    (socket, "create_connection"), (socket, "getaddrinfo"),
    (socket.socket, "connect"), (socket.socket, "connect_ex"),
]
for obj, name in targets:
    patch.object(obj, name, forbidden(name)).start()
code = pytest.main([
    "-c", "pyproject.toml", "tests/test_live_infrastructure.py",
    "--collect-only", "-q", "--showlocals", "-m", payload["markexpr"],
])
print("GUARD_PROBE=" + json.dumps({
    "exit_code": int(code), "calls": calls,
    "app_imports": [name for name in [
        "drip.core.config", "drip.core.database", "drip.core.redis", "drip.main"
    ] if name in sys.modules],
}))
'''


@pytest.mark.parametrize("overrides,missing,markexpr", [
    ({}, (PG_KEY, REDIS_KEY), "integration"),
    ({}, (PG_KEY,), "integration"),
    ({}, (REDIS_KEY,), "integration"),
    ({PG_KEY: ""}, (), "integration"),
    ({REDIS_KEY: ""}, (), "integration"),
    ({PG_KEY: POSTGRES_URL + "?host=never-log-this"}, (), "integration"),
    ({REDIS_KEY: "redis://:never-log-this@127.0.0.1:56381/0"}, (), "integration"),
    ({PG_KEY: "never-log-this", REDIS_KEY: "never-log-this"}, (), "integration"),
    ({PG_KEY: "never-log-this"}, (), "not integration"),
    ({REDIS_KEY: ""}, (), "not integration"),
    ({PG_KEY.lower(): "never-log-this"}, (PG_KEY, REDIS_KEY), "not integration"),
    ({"Drip_Test_Redis_Url": "never-log-this"}, (), "integration"),
], ids=["both-missing", "postgres-missing", "redis-missing", "postgres-empty", "redis-empty",
        "postgres-query", "redis-authority", "both-invalid", "nonlive-invalid", "nonlive-empty",
        "nonlive-postgres-alias", "live-redis-alias-with-exact"])
def test_real_pytest_startup_rejects_before_any_infrastructure_creation(overrides, missing, markexpr):
    environment = documented_environment() | overrides
    for key in missing:
        del environment[key]
    child_env = {key: value for key, value in os.environ.items() if key.upper() not in {
        PG_KEY, REDIS_KEY, "DATABASE_URL", "REDIS_URL", "DRIP_ENV_FILE", "ENVIRONMENT",
        "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
    }}
    child_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", STARTUP_PROBE], cwd=API_ROOT, env=child_env,
        input=json.dumps({"environment": environment, "markexpr": markexpr}),
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    assert "never-log-this" not in output
    assert POSTGRES_URL not in output
    assert REDIS_URL not in output
    marker = next(line for line in result.stdout.splitlines() if line.startswith("GUARD_PROBE="))
    evidence = json.loads(marker.removeprefix("GUARD_PROBE="))
    assert evidence == {"exit_code": 4, "calls": [], "app_imports": []}
    if any(key != key.upper() for key in overrides):
        assert "Test-target variables must use only the documented uppercase names." in result.stderr
    else:
        assert "must be the documented disposable" in result.stderr
