"""Exact INR output representation, separate from catalogue-price eligibility."""

from typing import Literal, TypedDict

MAX_AMOUNT_MINOR = 9223372036854775807


class MoneyINR(TypedDict):
    currency: Literal["INR"]
    amount_minor: str


def serialize_money_inr(amount_minor: int) -> MoneyINR:
    """Serialize built-in integer paise without parsing or business validation.

    General wire money allows zero; catalogue price records still require
    strictly positive paise. This does not authorize a price for publication.
    """
    if type(amount_minor) is not int:
        raise TypeError("amount_minor must be a Python int.")
    if not 0 <= amount_minor <= MAX_AMOUNT_MINOR:
        raise ValueError("amount_minor must be between 0 and 9223372036854775807.")
    return {"currency": "INR", "amount_minor": str(amount_minor)}
