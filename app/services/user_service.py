from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import User


def create_user(db: Session, name: str) -> User:
    exists = db.scalar(select(User.id).where(func.lower(User.name) == name.lower()))
    if exists is not None:
        raise ConflictError(f"A user named '{name}' already exists (names are case-insensitive)")
    user = User(name=name)
    db.add(user)
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user
