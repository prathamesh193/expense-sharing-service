from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Names are unique case-insensitively ("Mohit" == "mohit"). This keeps the
    # name-keyed balance view unambiguous.
    __table_args__ = (Index("uq_users_name_lower", func.lower(name), unique=True),)
