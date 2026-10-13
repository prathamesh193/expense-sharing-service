from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    return user_service.create_user(db, body.name)


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return user_service.list_users(db)
