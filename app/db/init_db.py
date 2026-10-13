"""Create all tables.  Usage:  python -m app.db.init_db"""
from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialised.")
