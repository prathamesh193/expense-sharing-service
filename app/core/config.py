"""Application settings, read from environment variables."""
import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./expense_sharing.db")
