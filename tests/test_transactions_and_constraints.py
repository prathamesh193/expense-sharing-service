"""Atomic expense creation and database-level integrity."""
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Expense, ExpenseParticipant, GroupMember
from app.services import expense_service


def test_rollback_when_participant_insert_fails(api, client, trip, session_factory, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated failure after the expense row was flushed")

    monkeypatch.setattr(expense_service, "_add_participants", boom)
    r = api.expense(trip["group"], trip["mohit"], 1200)
    assert r.status_code == 500

    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Expense)) == 0           # no orphan expense
        assert s.scalar(select(func.count()).select_from(ExpenseParticipant)) == 0
    assert client.get(f"/groups/{trip['group']}/expenses").json() == []


def test_successful_creation_writes_expense_and_all_participants(api, trip, session_factory):
    api.expense(trip["group"], trip["mohit"], "100.00")
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Expense)) == 1
        assert s.scalar(select(func.sum(ExpenseParticipant.share_paise))) == 10000


def test_db_rejects_payer_who_is_not_a_member(api, trip, session_factory):
    outsider = api.user("Outsider")
    with session_factory() as s:
        s.add(Expense(group_id=trip["group"], paid_by=outsider, amount_paise=100, description="x"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_db_rejects_non_positive_amount(trip, session_factory):
    with session_factory() as s:
        s.add(Expense(group_id=trip["group"], paid_by=trip["mohit"], amount_paise=0, description="x"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_db_rejects_duplicate_membership(trip, session_factory):
    with session_factory() as s:
        s.add(GroupMember(group_id=trip["group"], user_id=trip["mohit"]))
        with pytest.raises(IntegrityError):
            s.commit()


def test_db_rejects_dangling_foreign_key(trip, session_factory):
    with session_factory() as s:
        s.add(GroupMember(group_id=trip["group"], user_id=9999))
        with pytest.raises(IntegrityError):
            s.commit()


def test_db_enforces_case_insensitive_unique_user_names(api, session_factory):
    api.user("Mohit")
    with session_factory() as s:
        with pytest.raises(IntegrityError):
            s.execute(text("INSERT INTO users (name, created_at) VALUES ('MOHIT', CURRENT_TIMESTAMP)"))
            s.commit()


def test_no_expense_endpoint_mutates_history(client):
    # History is append-only through the API: no PUT/PATCH/DELETE routes exist for expenses.
    assert client.put("/expenses/1", json={}).status_code in (404, 405)
    assert client.delete("/expenses/1").status_code in (404, 405)
