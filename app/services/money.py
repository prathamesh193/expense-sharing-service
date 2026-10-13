"""Money helpers. All arithmetic in the app is on integer paise (1 INR = 100 paise)."""
from decimal import Decimal

PAISE_PER_RUPEE = 100


def rupees_to_paise(amount: Decimal) -> int:
    """Convert a validated Decimal rupee amount (max 2 decimal places) to integer paise."""
    paise = amount * PAISE_PER_RUPEE
    if paise != paise.to_integral_value():
        raise ValueError("amount has more than 2 decimal places")
    return int(paise)


def format_paise(paise: int) -> str:
    """Format integer paise as a rupee string with exactly two decimals, e.g. 40000 -> '400.00'."""
    sign = "-" if paise < 0 else ""
    rupees, rem = divmod(abs(paise), PAISE_PER_RUPEE)
    return f"{sign}{rupees}.{rem:02d}"
