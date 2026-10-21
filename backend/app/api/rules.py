"""/api/rules — צפייה, תצוגת השפעה ושמירה של קובץ הכללים. בעלות: מפתחת ב'.

"בפיילוט מחליפים נתונים, לא קוד": שינוי כאן נכנס לתוקף מיד בכל חישוב (המנוע קורא את הקובץ בכל פעם).
כל שמירה שומרת עותק של הגרסה הקודמת ב-config/history, ואפשר לבטל.
עריכה ותצוגת השפעה דורשות קוד גישה של מנהל/ת (app/auth.py). קריאת הכללים פתוחה.
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from app import seed
from app.auth import require_admin
from app.contracts import CompareRequest
from app.engine.compare import compare, demo_profile, demo_question_option
from app.engine.rules import Rules, load_rules

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _history():
    return seed.RULES_PATH.parent / "history"


class RulesBody(BaseModel):
    rules: dict


def _validate(raw: dict) -> Rules:
    try:
        return Rules.model_validate(raw)
    except ValidationError as e:
        problems = [f"{'.'.join(str(p) for p in err['loc']) or 'הקובץ'}: {err['msg']}" for err in e.errors()]
        raise HTTPException(422, {"message": "קובץ הכללים לא תקין", "problems": problems})


def _impact(rules: Rules) -> list[dict]:
    rows = []
    for e in seed.employees():
        option = demo_question_option(e["id"])
        resp = compare(CompareRequest(profile=demo_profile(e), alternatives=[option]), rules)
        alt = resp.alternatives[0]
        rows.append({
            "employee_id": e["id"],
            "name": e["name"],
            "group": e["group"],
            "alternative": alt.label,
            "status": alt.status,
            "net_today": resp.current.net,
            "net_alternative": alt.net,
            "delta": alt.delta_display,
        })
    return rows


@router.get("")
def get_rules():
    return seed.rules()


@router.post("/preview", dependencies=[Depends(require_admin)])
def preview(body: RulesBody):
    """מה ישתנה ל-6 העובדים לדוגמה אם נשמור את הכללים האלה. לא שומר כלום."""
    proposed = _validate(body.rules)
    before = {r["employee_id"]: r for r in _impact(load_rules())}
    rows = []
    for after in _impact(proposed):
        b = before[after["employee_id"]]
        rows.append({
            **after,
            "before": {k: b[k] for k in ("net_today", "net_alternative", "delta", "status")},
            "changed": any(
                (b[k] is None) != (after[k] is None) or (b[k] is not None and round(b[k]) != round(after[k]))
                for k in ("net_today", "net_alternative", "delta")
            ) or b["status"] != after["status"],
        })
    return {"valid": True, "version": proposed.version, "impact": rows}


@router.put("", dependencies=[Depends(require_admin)])
def save(body: RulesBody):
    _validate(body.rules)
    history = _history()
    history.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # מיקרו-שניות: שתי שמירות באותה שנייה לא דורסות גיבוי
    backup = history / f"strauss-rules.{stamp}.json"
    backup.write_text(seed.RULES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = seed.RULES_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(body.rules, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(seed.RULES_PATH)
    return {"saved": True, "version": body.rules.get("version"), "backup": backup.name}


@router.post("/undo", dependencies=[Depends(require_admin)])
def undo():
    """מחזיר את הגרסה האחרונה שנשמרה לפני השינוי."""
    history = _history()
    backups = sorted(history.glob("strauss-rules.*.json")) if history.exists() else []
    if not backups:
        raise HTTPException(404, "אין גרסה קודמת לשחזר")
    last = backups[-1]
    seed.RULES_PATH.write_text(last.read_text(encoding="utf-8"), encoding="utf-8")
    last.unlink()
    return {"restored": True, "version": seed.rules().get("version")}
