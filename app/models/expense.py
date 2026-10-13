from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User, utcnow


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    paid_by: Mapped[int] = mapped_column(nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)  # money is integer paise
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    payer: Mapped[User] = relationship(foreign_keys=[paid_by], primaryjoin="Expense.paid_by == User.id")
    participants: Mapped[list["ExpenseParticipant"]] = relationship(
        back_populates="expense", order_by="ExpenseParticipant.user_id", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_expenses_amount_positive"),
        # The payer must be a member of the expense's group - enforced by the DB itself,
        # not only by application code.
        ForeignKeyConstraint(
            ["group_id", "paid_by"],
            ["group_members.group_id", "group_members.user_id"],
            name="fk_expenses_payer_is_member",
        ),
        ForeignKeyConstraint(["paid_by"], ["users.id"], name="fk_expenses_paid_by_user"),
        Index("ix_expenses_group_created", "group_id", "created_at", "id"),
    )


class ExpenseParticipant(Base):
    """Snapshot of who was charged what when the expense was created.

    Written once, never updated: this is what keeps history stable when members join later.
    """

    __tablename__ = "expense_participants"

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    share_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    expense: Mapped[Expense] = relationship(back_populates="participants")
    user: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint("share_paise >= 0", name="ck_participants_share_non_negative"),
        Index("ix_expense_participants_user_id", "user_id"),
    )
