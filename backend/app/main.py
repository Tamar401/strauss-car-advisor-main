import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, chat, compare, data, payslip, rep, rules
from app.store import get_store

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    days = int(os.environ.get("RETENTION_DAYS", "30"))
    purged = get_store().purge_older_than(days)
    if purged:
        log.info("נמחקו %d שיחות ישנות מ-%d ימים", purged, days)
    yield


app = FastAPI(title="יועץ הרכב של שטראוס", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (accounts, data, compare, chat, payslip, rep, rules):
    app.include_router(module.router)


@app.get("/api/health")
def health():
    return {"ok": True}
