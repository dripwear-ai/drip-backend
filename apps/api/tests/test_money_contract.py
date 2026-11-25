import json
import subprocess
import sys
from decimal import Decimal
from enum import IntEnum
from pathlib import Path
from typing import cast

import pytest
from drip.contracts.money import serialize_money_inr


class IntSubclass(int):
    pass


class IntChoice(IntEnum):
    ONE = 1


class UnprintableInput:
    def __str__(self):
        raise AssertionError("Input must not be formatted")

    def __repr__(self):
        raise AssertionError("Input must not be formatted")


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, "0"),
        (1, "1"),
        (99, "99"),
        (100, "100"),
        (9007199254740993, "9007199254740993"),
        (9223372036854775806, "9223372036854775806"),
        (9223372036854775807, "9223372036854775807"),
    ],
    ids=["zero", "one", "small", "one-rupee", "above-js-safe", "below-max", "max"],
)
def test_lossless_money_output_and_json(amount, expected):
    # General wire money allows zero; catalogue price eligibility remains strictly positive.
    result = serialize_money_inr(amount)
    assert result == {"currency": "INR", "amount_minor": expected}
    assert type(result["amount_minor"]) is str
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    assert encoded == '{"amount_minor":"' + expected + '","currency":"INR"}'
    assert json.loads(encoded) == result


@pytest.mark.parametrize(
    "value",
    [-1, -9223372036854775808, 9223372036854775808, 10**100],
    ids=["negative", "signed-min", "overflow", "large-overflow"],
)
def test_out_of_range_amount_has_fixed_error(value):
    with pytest.raises(ValueError) as exc:
        serialize_money_inr(value)
    assert str(exc.value) == "amount_minor must be between 0 and 9223372036854775807."


@pytest.mark.parametrize(
    "value",
    [
        True, False, 0.0, 1.0, float("nan"), float("inf"), "0", "123",
        "synthetic-private-input", None, b"1", Decimal("1"), IntSubclass(1),
        IntChoice.ONE, [], {}, UnprintableInput(),
    ],
    ids=[
        "true", "false", "float-zero", "float-one", "nan", "infinity", "string-zero",
        "string-number", "private-string", "none", "bytes", "decimal", "int-subclass",
        "int-enum", "list", "dict", "unprintable",
    ],
)
def test_non_builtin_integer_has_fixed_redacted_error(value):
    with pytest.raises(TypeError) as exc:
        serialize_money_inr(cast(int, value))
    assert str(exc.value) == "amount_minor must be a Python int."


def test_money_import_and_serialization_do_not_load_infrastructure():
    source = Path(__file__).resolve().parents[1] / "src"
    script = """
import importlib.abc
import sys

class DenyInfrastructure(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = ('drip.core', 'drip.main', 'sqlalchemy', 'redis', 'httpx',
                   'requests', 'logging', 'socket')
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise AssertionError('Unexpected infrastructure import')

sys.meta_path.insert(0, DenyInfrastructure())
sys.path.insert(0, sys.argv[1])
from drip.contracts.money import serialize_money_inr
assert serialize_money_inr(0) == {'currency': 'INR', 'amount_minor': '0'}
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(source)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
