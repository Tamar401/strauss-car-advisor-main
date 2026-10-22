import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, chat, compare, data, payslip, rep, rules
from app.engine import vou
from app.store import get_store

log = logging.getLogger(__name__)
PRODUCTION_FRONTEND_ORIGIN = "https://strauss-car-advisor-frontend.onrender.com"
KEEP_ALIVE_SECONDS = 10 * 60  # השרת החינמי של Render נרדם אחרי 15 דקות בלי בקשות


def _allowed_origins() -> list[str]:
    configured = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    origins = {origin.strip().rstrip("/") for origin in configured if origin.strip().rstrip("/")}
    origins.add(PRODUCTION_FRONTEND_ORIGIN)
    return sorted(origins)


async def _keep_alive(url: str) -> None:
    """פונה לכתובת הציבורית של השרת עצמו, כדי ש-Render יראה תנועה ולא ירדים אותו."""
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            await asyncio.sleep(KEEP_ALIVE_SECONDS)
            try:
                await client.get(f"{url}/api/health")
            except httpx.HTTPError as e:
                log.warning("keep-alive נכשל: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    days = int(os.environ.get("RETENTION_DAYS", "30"))
    purged = get_store().purge_older_than(days)
    if purged:
        log.info("נמחקו %d שיחות ישנות מ-%d ימים", purged, days)
    vou.lookup_ready()  # בונה את מאגר שווי השימוש עכשיו, ולא בשאלה הראשונה של עובד
    url = os.environ.get("RENDER_EXTERNAL_URL")  # Render מגדיר אותו לבד; מקומית — אין keep-alive
    task = asyncio.create_task(_keep_alive(url.rstrip("/"))) if url else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="יועץ הרכב של שטראוס", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (accounts, data, compare, chat, payslip, rep, rules):
    app.include_router(module.router)


@app.get("/api/health")
def health():
    return {"ok": True}
