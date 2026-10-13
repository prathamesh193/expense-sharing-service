from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Group, GroupMember, User
from app.services.user_service import get_user_or_404


def create_group(db: Session, name: str) -> Group:
    group = Group(name=name)
    db.add(group)
    db.commit()
    return group


def list_groups(db: Session) -> list[Group]:
    return list(db.scalars(select(Group).order_by(Group.id)))


def get_group_or_404(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise NotFoundError(f"Group {group_id} not found")
    return group


def add_member(db: Session, group_id: int, user_id: int, body_group_id: int | None = None) -> tuple[User, GroupMember]:
    if body_group_id is not None and body_group_id != group_id:
        raise BusinessRuleError("group_id in the body does not match the group_id in the URL")
    get_group_or_404(db, group_id)
    user = get_user_or_404(db, user_id)
    if db.get(GroupMember, (group_id, user_id)) is not None:
        # Policy: repeating a membership request is a conflict, not a silent success.
        raise ConflictError(f"User {user_id} is already a member of group {group_id}")
    member = GroupMember(group_id=group_id, user_id=user_id)
    db.add(member)
    db.commit()
    return user, member


def list_members(db: Session, group_id: int) -> list[tuple[User, GroupMember]]:
    """Members of a group (an empty group returns an empty list), ordered by user id."""
    get_group_or_404(db, group_id)
    stmt = (
        select(User, GroupMember)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
        .order_by(User.id)
    )
    return [(u, m) for u, m in db.execute(stmt).all()]


def member_ids(db: Session, group_id: int) -> list[int]:
    return list(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id == group_id).order_by(GroupMember.user_id)))
