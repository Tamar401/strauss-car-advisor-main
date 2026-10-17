"""נתוני עזר: קטלוג, עיסוקים, עובדים לדוגמה (קורא מה-seed). הכללים — ב-api/rules.py."""
from fastapi import APIRouter, Depends, Header, HTTPException

from app import seed
from app.agent.tools import vehicle_candidate
from app.auth import allowed, require
from app.contracts import Car, Occupation
from app.engine import vou

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/catalog", response_model=list[Car])
def get_catalog():
    return seed.catalog()


@router.get("/occupations", response_model=list[Occupation])
def get_occupations():
    return seed.occupations()


@router.get("/vehicles/search", dependencies=[Depends(require("rep"))])
def search_vehicles(q: str, year: int | None = None):
    """חיפוש במאגר רשות המסים — למסך הנציג, כשצריך לזהות את הרכב של העובד היום."""
    rows, total = vou.search(q, year, limit=30)
    return {"total": total, "candidates": [vehicle_candidate(r) for r in rows]}


@router.get("/demo-employees")
def get_demo_employees():
    """6 העובדים לדוגמה — לכפתורי "מלא נתוני דמו" בהדגמה. בלי ת״ז."""
    return [{k: v for k, v in e.items() if k != "national_id"} for e in seed.employees()]


@router.get("/auth/check/{role}")
def check_access(role: str, x_access_code: str | None = Header(default=None)):
    """לממשק: האם הקוד שהוקלד פותח את המסך."""
    if role not in ("rep", "admin"):
        raise HTTPException(404)
    if not allowed(role, x_access_code):
        raise HTTPException(401, "קוד גישה שגוי")
    return {"ok": True}
