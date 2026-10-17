"""השוואת חלופות — המנוע האמיתי (app/engine). בעלות: מפתחת א'."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import seed
from app.contracts import CompareRequest, CompareResponse, EmployeeProfile
from app.engine.compare import compare, compare_all, demo_profile

router = APIRouter(prefix="/api", tags=["compare"])


class CompareAllRequest(BaseModel):
    profile: EmployeeProfile


@router.post("/compare", response_model=CompareResponse)
def compare_options(req: CompareRequest):
    try:
        return compare(req)
    except (ValueError, LookupError) as e:
        raise HTTPException(400, str(e))


@router.post("/compare/all", response_model=CompareResponse)
def compare_all_options(req: CompareAllRequest):
    """כל רכב בקטלוג + ויתור, ממוין מהחלופה הטובה ביותר."""
    return compare_all(req.profile)


@router.get("/demo/compare/{employee_id}", response_model=CompareResponse)
def demo_compare(employee_id: str):
    """השוואה מלאה לאחד מ-6 העובדים לדוגמה — להדגמה ולעמוד /design."""
    employee = next((e for e in seed.employees() if e["id"] == employee_id), None)
    if employee is None:
        raise HTTPException(404, "עובד לדוגמה לא נמצא")
    return compare_all(demo_profile(employee))
