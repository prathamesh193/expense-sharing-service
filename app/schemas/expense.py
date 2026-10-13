from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models import Expense
from app.services.money import format_paise

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ExpenseCreate(BaseModel):
    group_id: int = Field(gt=0)
    paid_by: int = Field(gt=0)
    # Rupees, at most 2 decimal places (e.g. 1200 or 1200.50). Converted to integer paise.
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    description: Description


class ParticipantOut(BaseModel):
    user_id: int
    name: str
    share: str
    share_paise: int


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    description: str
    amount: str
    amount_paise: int
    paid_by: str  # payer's name (matches the assignment's example response)
    paid_by_id: int
    created_at: datetime
    participants: list[ParticipantOut]

    @classmethod
    def from_model(cls, e: Expense) -> "ExpenseOut":
        return cls(
            id=e.id,
            group_id=e.group_id,
            description=e.description,
            amount=format_paise(e.amount_paise),
            amount_paise=e.amount_paise,
            paid_by=e.payer.name,
            paid_by_id=e.paid_by,
            created_at=e.created_at,
            participants=[
                ParticipantOut(
                    user_id=p.user_id,
                    name=p.user.name,
                    share=format_paise(p.share_paise),
                    share_paise=p.share_paise,
                )
                for p in e.participants
            ],
        )
