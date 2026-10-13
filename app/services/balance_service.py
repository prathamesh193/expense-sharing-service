"""Glue between the database and the pure balance engine."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseParticipant, User
from app.schemas.balance import (
    BalanceEntry,
    BalancesOut,
    NetBalanceEntry,
    Scope,
    SettlementPayment,
    SettlementsOut,
)
from app.schemas.user import UserOut
from app.services import balance_engine as engine
from app.services.balance_engine import Debt
from app.services.group_service import get_group_or_404
from app.services.money import format_paise


def _load_debts(db: Session, group_id: int | None) -> list[Debt]:
    """Aggregate stored shares into (participant owes payer) totals. Payer's own share is skipped."""
    stmt = (
        select(ExpenseParticipant.user_id, Expense.paid_by, func.sum(ExpenseParticipant.share_paise))
        .join(Expense, Expense.id == ExpenseParticipant.expense_id)
        .where(ExpenseParticipant.user_id != Expense.paid_by, ExpenseParticipant.share_paise > 0)
        .group_by(ExpenseParticipant.user_id, Expense.paid_by)
    )
    if group_id is not None:
        stmt = stmt.where(Expense.group_id == group_id)
    return [Debt(debtor=d, creditor=c, amount_paise=int(total)) for d, c, total in db.execute(stmt).all()]


def _users_by_id(db: Session, ids: set[int]) -> dict[int, UserOut]:
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: UserOut.model_validate(u) for u in users}


def get_balances(db: Session, group_id: int | None = None) -> BalancesOut:
    """group_id=None -> system-wide (all groups combined); otherwise that group only."""
    if group_id is not None:
        get_group_or_404(db, group_id)
    pairs = engine.pairwise_balances(_load_debts(db, group_id))
    net = engine.net_balances(pairs)
    users = _users_by_id(db, {p.debtor for p in pairs} | {p.creditor for p in pairs})

    owes: dict[str, dict[str, dict[str, str]]] = {}
    for p in pairs:
        owes.setdefault(users[p.debtor].name, {"owes": {}})["owes"][users[p.creditor].name] = format_paise(p.amount_paise)

    return BalancesOut(
        scope=Scope(type="group" if group_id is not None else "all_groups", group_id=group_id),
        balances=[
            BalanceEntry(
                debtor=users[p.debtor], creditor=users[p.creditor],
                amount=format_paise(p.amount_paise), amount_paise=p.amount_paise,
            )
            for p in pairs
        ],
        owes=owes,
        net_balances=[
            NetBalanceEntry(user=users[uid], net=format_paise(v), net_paise=v) for uid, v in net.items()
        ],
    )


def get_settlement_suggestions(db: Session, group_id: int) -> SettlementsOut:
    """Product enhancement: read-only. Nothing is written to the database."""
    get_group_or_404(db, group_id)
    net = engine.net_balances(engine.pairwise_balances(_load_debts(db, group_id)))
    payments = engine.suggest_settlements(net)
    users = _users_by_id(db, {p.debtor for p in payments} | {p.creditor for p in payments})
    return SettlementsOut(
        group_id=group_id,
        is_settled=not payments,
        payment_count=len(payments),
        suggested_payments=[
            SettlementPayment(
                from_user=users[p.debtor], to_user=users[p.creditor],
                amount=format_paise(p.amount_paise), amount_paise=p.amount_paise,
            )
            for p in payments
        ],
    )
