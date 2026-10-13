from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BusinessRuleError
from app.models import Expense, ExpenseParticipant
from app.services import group_service
from app.services.balance_engine import split_equally
from app.services.user_service import get_user_or_404


def _add_participants(db: Session, expense_id: int, shares: dict[int, int]) -> None:
    db.add_all(
        ExpenseParticipant(expense_id=expense_id, user_id=uid, share_paise=share)
        for uid, share in shares.items()
    )


def create_expense(db: Session, group_id: int, paid_by: int, amount_paise: int, description: str) -> Expense:
    """Validate, split equally among the group's *current* members, and persist atomically.

    The expense row and all participant rows are committed together or not at all.
    """
    if amount_paise <= 0:
        raise BusinessRuleError("amount must be greater than 0")
    group_service.get_group_or_404(db, group_id)
    get_user_or_404(db, paid_by)
    members = group_service.member_ids(db, group_id)
    if paid_by not in members:
        raise BusinessRuleError(f"User {paid_by} is not a member of group {group_id}")

    shares = split_equally(amount_paise, members)  # payer is included; their own share is simply never owed
    try:
        expense = Expense(group_id=group_id, paid_by=paid_by, amount_paise=amount_paise, description=description)
        db.add(expense)
        db.flush()  # assigns expense.id inside the open transaction
        _add_participants(db, expense.id, shares)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_expense(db, expense.id)


def get_expense(db: Session, expense_id: int) -> Expense:
    return db.scalars(_with_details(select(Expense).where(Expense.id == expense_id))).one()


def list_expenses(db: Session, group_id: int) -> list[Expense]:
    """Chronological (oldest first); id breaks ties so the order is always stable."""
    group_service.get_group_or_404(db, group_id)
    stmt = select(Expense).where(Expense.group_id == group_id).order_by(Expense.created_at, Expense.id)
    return list(db.scalars(_with_details(stmt)))


def _with_details(stmt):  # noqa: ANN001, ANN202
    return stmt.options(
        selectinload(Expense.payer),
        selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
    )
