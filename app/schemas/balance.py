from typing import Literal, Optional

from pydantic import BaseModel

from app.schemas.user import UserOut


class Scope(BaseModel):
    type: Literal["group", "all_groups"]
    group_id: Optional[int] = None


class BalanceEntry(BaseModel):
    debtor: UserOut
    creditor: UserOut
    amount: str
    amount_paise: int


class NetBalanceEntry(BaseModel):
    user: UserOut
    net: str  # signed: positive = is owed money, negative = owes money
    net_paise: int


class BalancesOut(BaseModel):
    scope: Scope
    currency: str = "INR"
    balances: list[BalanceEntry]
    # Same data as `balances`, shaped like the assignment's example: {"Rahul": {"owes": {"Mohit": "400.00"}}}
    owes: dict[str, dict[str, dict[str, str]]]
    net_balances: list[NetBalanceEntry]


class SettlementPayment(BaseModel):
    from_user: UserOut
    to_user: UserOut
    amount: str
    amount_paise: int


class SettlementsOut(BaseModel):
    group_id: int
    currency: str = "INR"
    is_settled: bool
    payment_count: int
    suggested_payments: list[SettlementPayment]
    note: str = "Suggestions only. Recording or following them does not change any balance."
