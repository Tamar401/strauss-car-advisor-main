"""מאגר שווי השימוש של רשות המסים (77,988 רשומות) ב-SQLite.

השליפה תמיד לפי המפתח המלא: שנת מס + שנת רישום + קוד סוג רכב + קוד תוצר + קוד דגם.
בלי קוד סוג רכב יש התנגשויות אמיתיות (BYD 01014/00003 = ATTO 3 וגם TANG) — ראו docs/DATA_FINDINGS.md.
ה-DB נבנה מה-CSV בפעם הראשונה ונשמר ב-data/vou.db (לא נכנס ל-git).
"""
from __future__ import annotations

import csv
import sqlite3
from functools import lru_cache
from pathlib import Path

from app.contracts import VouKey
from app.seed import ROOT, VOU_CSV

DB_PATH = ROOT / "data" / "vou.db"

# סדר העמודות ב-CSV (הכותרות בעברית ובקידוד cp1255 — מסתמכים על המיקום)
COLUMNS = [
    "tax_year",
    "registration_year",
    "vehicle_type_code",
    "manufacturer_code",
    "manufacturer",
    "model_code",
    "model_description",
    "fuel_code",
    "commercial_name",
    "automatic",
    "drive_code",  # 0 בנזין · 1 היברידי · 2 פלאג-אין · 3 חשמלי (הכותרת בקובץ שגויה)
    "green_score",
    "pollution_level",
    "engine_cc",
    "weight",
    "effective_date",
    "list_price",
    "adjusted_price",
    "value_of_use",
]
INT_COLUMNS = {"tax_year", "registration_year", "vehicle_type_code", "drive_code"}
FLOAT_COLUMNS = {"list_price", "adjusted_price", "value_of_use"}
KEY = ["tax_year", "registration_year", "vehicle_type_code", "manufacturer_code", "model_code"]


def build_db(csv_path: Path = VOU_CSV, db_path: Path = DB_PATH) -> int:
    def parse(row):
        out = {}
        for name, raw in zip(COLUMNS, row):
            value = raw.strip()
            if name in INT_COLUMNS:
                out[name] = int(value)
            elif name in FLOAT_COLUMNS:
                out[name] = float(value)
            else:
                out[name] = value  # קודים נשמרים כמחרוזת — עם האפסים המובילים
        return out

    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.execute(f"CREATE TABLE vou ({', '.join(COLUMNS)}, PRIMARY KEY ({', '.join(KEY)}))")
    with open(csv_path, encoding="cp1255", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        rows = [parse(r) for r in reader if r]
    con.executemany(
        f"INSERT INTO vou VALUES ({', '.join(':' + c for c in COLUMNS)})",
        rows,
    )
    con.execute("CREATE INDEX idx_model ON vou (registration_year, manufacturer_code, model_code)")
    con.commit()
    con.close()
    tmp.replace(db_path)
    return len(rows)


@lru_cache
def _connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        build_db()
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def lookup_ready() -> None:
    _connection()


def lookup(key: VouKey) -> dict | None:
    row = _connection().execute(
        f"SELECT * FROM vou WHERE {' AND '.join(f'{k} = ?' for k in KEY)}",
        [getattr(key, k) for k in KEY],
    ).fetchone()
    return dict(row) if row else None


@lru_cache
def resolve_catalog_car(
    registration_year: int, manufacturer_code: str, model_code: str, model_description: str, tax_year: int = 2026
) -> VouKey:
    """לקטלוג אין קוד סוג רכב. משלימים אותו לפי תאור הדגם, ומסרבים אם התוצאה לא חד-משמעית."""
    rows = _connection().execute(
        "SELECT * FROM vou WHERE tax_year = ? AND registration_year = ? AND manufacturer_code = ? AND model_code = ?",
        (tax_year, registration_year, manufacturer_code, model_code),
    ).fetchall()
    matches = [r for r in rows if r["model_description"] == model_description.strip()]
    if len(matches) != 1:
        raise LookupError(
            f"לא נמצאה התאמה חד-משמעית במאגר ל-{manufacturer_code}/{model_code} ({registration_year}, "
            f"{model_description}): {len(matches)} תוצאות"
        )
    return VouKey(**{k: matches[0][k] for k in KEY})


def key_of(row: dict) -> VouKey:
    return VouKey(**{k: row[k] for k in KEY})


def key_text(key: VouKey) -> str:
    return f"{key.tax_year}/{key.registration_year}/{key.vehicle_type_code}/{key.manufacturer_code}/{key.model_code}"


def parse_key(text: str) -> VouKey:
    parts = text.strip().split("/")
    if len(parts) != 5:
        raise ValueError(f"מפתח לא תקין: {text}")
    return VouKey(
        tax_year=int(parts[0]), registration_year=int(parts[1]), vehicle_type_code=int(parts[2]),
        manufacturer_code=parts[3], model_code=parts[4],
    )


def search(text: str, registration_year: int | None = None, limit: int = 12, tax_year: int = 2026) -> tuple[list[dict], int]:
    """חיפוש רכב כפי שעובד מתאר אותו: כל מילה חייבת להופיע ביצרן, בכינוי המסחרי, בתאור הדגם או בקוד הדגם.

    מחזיר (התאמות, סה"כ). אותו כינוי ושנה מופיעים לרוב בכמה רמות גימור עם שווי שימוש שונה —
    לכן מחזירים את כולן (עד limit) ולא בוחרים אחת.
    """
    words = [w for w in text.upper().split() if w]
    if not words:
        return [], 0
    where = ["tax_year = ?"]
    params: list = [tax_year]
    for w in words:
        where.append("(UPPER(manufacturer) LIKE ? OR UPPER(commercial_name) LIKE ? OR UPPER(model_description) LIKE ? OR model_code = ?)")
        params += [f"%{w}%", f"%{w}%", f"%{w}%", w.zfill(5) if w.isdigit() else w]
    if registration_year is not None:
        where.append("registration_year = ?")
        params.append(registration_year)
    condition = " AND ".join(where)
    con = _connection()
    total = con.execute(f"SELECT COUNT(*) FROM vou WHERE {condition}", params).fetchone()[0]
    rows = con.execute(
        f"SELECT * FROM vou WHERE {condition} ORDER BY registration_year DESC, commercial_name, list_price LIMIT ?",
        [*params, limit],
    ).fetchall()
    return [dict(r) for r in rows], total
