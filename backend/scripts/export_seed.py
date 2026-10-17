"""ייצוא נתוני האתגר מהאקסל לקבצי JSON ב-data/seed.

הרצה (מתיקיית backend):  python scripts/export_seed.py
הקבצים שנוצרים: catalog.json, occupations.json, employees.json, golden.json
golden.json = נטו הייחוס של 6 העובדים — הבדיקות של המנוע משוות אליו.
"""
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
XLSX = ROOT / "data" / "raw" / "challenge_data.xlsx"
OUT = ROOT / "data" / "seed"

DRIVE = {"בנזין": "petrol", "היברידי": "hybrid", "פלאג-אין": "plugin", "חשמלי": "electric"}
YES = {"כן": True, "לא": False}


def rows(ws):
    it = ws.iter_rows(values_only=True)
    next(it)  # כותרות
    return [r for r in it if r[0] is not None]


def catalog(ws):
    return [
        {
            "id": r[0],
            "group": r[1],
            "manufacturer": r[2],
            "manufacturer_code": r[3],
            "model": r[4],
            "model_code": r[5],
            "model_description": r[6],
            "registration_year": r[7],
            "drive": DRIVE[r[8]],
            "list_price": r[9],
            "value_of_use": r[10],
            "monthly_cost": r[11],
            "default_participation": r[12],
        }
        for r in rows(ws)
    ]


def occupations(ws):
    return [
        {
            "name": r[0],
            "group": r[1],
            "car_required": YES[r[2]],
            "waiver_allowed": YES[r[3]],
            "waiver_maintenance": r[4],
        }
        for r in rows(ws)
    ]


def employees(ws, cars):
    by_model = {c["model"]: c["id"] for c in cars}
    out = []
    for r in rows(ws):
        current = r[12]
        if current.startswith("אין"):
            # "אין (אחזקה 1500 ₪)" — העובדת מקבלת היום אחזקת רכב
            current_option = {"kind": "waiver"}
        else:
            current_option = {"kind": "car", "car_id": by_model[current]}
        out.append(
            {
                "id": r[0],
                "name": r[1],
                "national_id": r[2],
                "occupation": r[3],
                "group": r[4],
                "base_salary": r[5],
                "commissions": r[6],
                "bonus": r[7],
                "pension_pct": r[8],
                "study_fund_pct": r[9],
                "credit_points": r[10],
                "children_under_23": r[11],
                "current_option": current_option,
                "current_participation": r[13],
                "question": r[14],
            }
        )
    return out


def golden(ws):
    return [
        {
            "employee_id": r[0],
            "today": r[2],
            "alternative": r[3],
            "eligible": YES[r[4]],
            "net_today": r[6],
            "net_alternative": r[7],
            "delta": r[8],
            "tax_today": r[9],
            "tax_alternative": r[10],
            "ni_health_today": r[11],
            "ni_health_alternative": r[12],
            "electric_gross": r[13],
            "family_gap_employee": r[14],
            "why": r[15],
        }
        for r in rows(ws)
    ]


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    cars = catalog(wb["קטלוג רכבים"])
    data = {
        "catalog.json": cars,
        "occupations.json": occupations(wb["עיסוקים"]),
        "employees.json": employees(wb["עובדים לדוגמה"], cars),
        "golden.json": golden(wb["חישובים"]),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in data.items():
        (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name}: {len(payload)} records")


if __name__ == "__main__":
    main()
