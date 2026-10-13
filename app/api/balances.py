from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.balance import BalancesOut
from app.services import balance_service

router = APIRouter(prefix="/balances", tags=["Balances"])


@router.get("", response_model=BalancesOut)
def get_balances(
    group_id: Optional[int] = Query(default=None, gt=0, description="Omit for system-wide balances"),
    db: Session = Depends(get_db),
):
    return balance_service.get_balances(db, group_id)
