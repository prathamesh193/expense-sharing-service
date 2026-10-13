from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.expense import ExpenseCreate, ExpenseOut
from app.services import expense_service
from app.services.money import rupees_to_paise

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseCreate, db: Session = Depends(get_db)):
    expense = expense_service.create_expense(
        db, body.group_id, body.paid_by, rupees_to_paise(body.amount), body.description
    )
    return ExpenseOut.from_model(expense)
