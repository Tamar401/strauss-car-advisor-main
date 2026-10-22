import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts, chat, compare, data, payslip, rep, rules
from app.auth import hash_password, normalize_email
from app.engine import vou
from app.store import get_store

log = logging.getLogger(__name__)
PRODUCTION_FRONTEND_ORIGIN = "https://strauss-car-advisor-frontend.onrender.com"
KEEP_ALIVE_SECONDS = 10 * 60  # השרת החינמי של Render נרדם אחרי 15 דקות בלי בקשות
PURGE_SECONDS = 24 * 60 * 60


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


def _purge(days: int) -> None:
    purged = get_store().purge_older_than(days)
    if purged:
        log.info("נמחקו %d שיחות ישנות מ-%d ימים", purged, days)


async def _purge_daily(days: int) -> None:
    """בזכות ה-keep-alive השרת כמעט לא עולה מחדש — לכן המחיקה רצה גם כל יום, לא רק בעלייה."""
    while True:
        await asyncio.sleep(PURGE_SECONDS)
        try:
            _purge(days)
        except Exception:
            log.exception("מחיקת שיחות ישנות נכשלה")


def _seed_demo_rep() -> None:
    email = os.environ.get("DEMO_REP_EMAIL", "").strip()
    password = os.environ.get("DEMO_REP_PASSWORD", "")
    if not email:
        return
    if len(password) < 12:
        log.warning("DEMO_REP_PASSWORD חייבת להיות באורך 12 תווים לפחות; חשבון נציג ההדגמה לא נוצר")
        return
    try:
        email = normalize_email(email)
    except HTTPException:
        log.warning("DEMO_REP_EMAIL אינה כתובת דוא״ל תקינה; חשבון נציג ההדגמה לא נוצר")
        return
    if not get_store().upsert_demo_rep(email, hash_password(password)):
        log.warning("DEMO_REP_EMAIL כבר שייך לחשבון אחר; חשבון נציג ההדגמה לא נוצר")


@asynccontextmanager
async def lifespan(app: FastAPI):
    days = int(os.environ.get("RETENTION_DAYS", "30"))
    _purge(days)
    _seed_demo_rep()
    vou.lookup_ready()  # בונה את מאגר שווי השימוש עכשיו, ולא בשאלה הראשונה של עובד
    tasks = [asyncio.create_task(_purge_daily(days))]
    url = os.environ.get("RENDER_EXTERNAL_URL")  # Render מגדיר אותו לבד; מקומית — אין keep-alive
    if url:
        tasks.append(asyncio.create_task(_keep_alive(url.rstrip("/"))))
    yield
    for task in tasks:
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
