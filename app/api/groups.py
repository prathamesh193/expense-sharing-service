from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.balance import BalancesOut, SettlementsOut
from app.schemas.expense import ExpenseOut
from app.schemas.group import GroupCreate, GroupOut, MemberAdd, MemberOut
from app.services import balance_service, expense_service, group_service

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupCreate, db: Session = Depends(get_db)):
    return group_service.create_group(db, body.name)


@router.get("", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db)):
    return group_service.list_groups(db)


@router.post("/{group_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(group_id: int, body: MemberAdd, db: Session = Depends(get_db)):
    user, member = group_service.add_member(db, group_id, body.user_id, body.group_id)
    return MemberOut(id=user.id, name=user.name, joined_at=member.joined_at)


@router.get("/{group_id}/members", response_model=list[MemberOut])
def list_members(group_id: int, db: Session = Depends(get_db)):
    return [MemberOut(id=u.id, name=u.name, joined_at=m.joined_at) for u, m in group_service.list_members(db, group_id)]


@router.get("/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(group_id: int, db: Session = Depends(get_db)):
    return [ExpenseOut.from_model(e) for e in expense_service.list_expenses(db, group_id)]


@router.get("/{group_id}/balances", response_model=BalancesOut)
def group_balances(group_id: int, db: Session = Depends(get_db)):
    return balance_service.get_balances(db, group_id)


@router.get("/{group_id}/settlements", response_model=SettlementsOut)
def settlement_suggestions(group_id: int, db: Session = Depends(get_db)):
    return balance_service.get_settlement_suggestions(db, group_id)
