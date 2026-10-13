from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import Name


class GroupCreate(BaseModel):
    name: Name


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MemberAdd(BaseModel):
    user_id: int = Field(gt=0)
    # Accepted for compatibility with the assignment's example body; must match the URL if sent.
    group_id: Optional[int] = Field(default=None, gt=0)


class MemberOut(BaseModel):
    id: int
    name: str
    joined_at: datetime
