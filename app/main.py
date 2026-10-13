from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import balances, expenses, groups, users
from app.core.errors import register_error_handlers
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # idempotent: creates missing tables only
    yield


app = FastAPI(title="Expense Sharing Service", version="1.0.0", lifespan=lifespan)
register_error_handlers(app)
for module in (users, groups, expenses, balances):
    app.include_router(module.router)


@app.get("/health", tags=["Meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
