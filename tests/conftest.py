"""Every test gets its own brand-new in-memory SQLite database - no shared state, no order dependence."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (register tables)
from app.db.base import Base
from app.db.session import build_engine, get_db
from app.main import app


@pytest.fixture()
def session_factory():
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with` block: we do not want the lifespan creating tables in the real database file.
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class Api:
    """Small helper so tests read like scenarios."""

    def __init__(self, client: TestClient) -> None:
        self.c = client

    def user(self, name: str) -> int:
        r = self.c.post("/users", json={"name": name})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def group(self, name: str = "Goa Trip", members: tuple[int, ...] = ()) -> int:
        r = self.c.post("/groups", json={"name": name})
        assert r.status_code == 201, r.text
        gid = r.json()["id"]
        for uid in members:
            self.add_member(gid, uid)
        return gid

    def add_member(self, gid: int, uid: int):
        r = self.c.post(f"/groups/{gid}/members", json={"user_id": uid})
        assert r.status_code == 201, r.text
        return r

    def expense(self, gid: int, paid_by: int, amount, description: str = "Dinner"):
        return self.c.post(
            "/expenses", json={"group_id": gid, "paid_by": paid_by, "amount": amount, "description": description}
        )

    def balances(self, gid: int | None = None) -> dict:
        r = self.c.get("/balances" if gid is None else f"/balances?group_id={gid}")
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture()
def api(client) -> Api:
    return Api(client)


@pytest.fixture()
def trip(api):
    """Mohit, Rahul, Ankit in 'Goa Trip' - the assignment's example."""
    m, r, a = api.user("Mohit"), api.user("Rahul"), api.user("Ankit")
    g = api.group("Goa Trip", (m, r, a))
    return {"mohit": m, "rahul": r, "ankit": a, "group": g}
