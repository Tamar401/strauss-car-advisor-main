"""Number Guard: כל מספר בתשובת הבוט חייב להגיע ממקור מאומת.

מקורות מאומתים בלבד:
  1. תוצאות הכלים בשיחה הזו (מה שהמנוע / המאגר / הקטלוג החזירו בפועל)
  2. הפרופיל, וההשתתפויות שהעובד או הנציג מסרו
  3. קובץ הכללים (תקציבים, החזר חשמל וכו' — מופיעים גם בפרומפט)
  4. מה שהעובד עצמו כתב
סכום בש״ח או אחוז חייבים מקור תמיד. מספר "חשוף" קטן (ספירה, מספר דגם כמו EV3) או שנה — מותר.
"""
from __future__ import annotations

import math
import re

from app.contracts import CompareResponse, OptionResult
from app.engine.rules import Rules
from app.store import ConversationRecord

NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
CURRENCY_AFTER = re.compile(r"^\s?(?:₪|ש[״\"']ח|שקל)")
PERCENT_AFTER = re.compile(r"^\s?%")
CURRENCY_BEFORE = re.compile(r"₪\s?$")
SMALL = 12
YEARS = range(2015, 2031)
MONEY_TOLERANCE = 1.0  # עיגול לשקל בתצוגה
PCT_TOLERANCE = 0.01


def numbers_in(text: str) -> list[float]:
    return [float(m.replace(",", "")) for m in NUMBER.findall(text)]


def tokens(text: str) -> list[tuple[float, str]]:
    """כל מספר עם הסוג שלו: money / percent / bare."""
    out = []
    for m in NUMBER.finditer(text):
        value = float(m.group().replace(",", ""))
        after, before = text[m.end():m.end() + 4], text[max(0, m.start() - 2):m.start()]
        if PERCENT_AFTER.match(after):
            kind = "percent"
        elif CURRENCY_AFTER.match(after) or CURRENCY_BEFORE.search(before):
            kind = "money"
        else:
            kind = "bare"
        out.append((value, kind))
    return out


def _walk_numbers(obj) -> set[float]:
    """כל המספרים בתוך תוצאת כלי (dict / list / מחרוזות עם מספרים)."""
    found: set[float] = set()
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.add(abs(float(obj)))
    elif isinstance(obj, str):
        found |= set(numbers_in(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            found |= _walk_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found |= _walk_numbers(v)
    return found


def tool_output_numbers(history: list[dict]) -> set[float]:
    """המספרים בכל תוצאות הכלים שהמודל קיבל בשיחה (ההיסטוריה כ-JSON)."""
    found: set[float] = set()
    for content in history:
        for part in content.get("parts", []) or []:
            response = (part.get("function_response") or {}).get("response")
            if response is not None:
                found |= _walk_numbers(response)
    return found


def _result_numbers(r: OptionResult) -> set[float]:
    values = {
        r.budget, r.monthly_cost, r.employee_participation, r.family_gap_employee, r.value_of_use,
        r.electric_bonus_gross, r.maintenance, r.gross, r.taxable_income, r.income_tax,
        r.national_insurance, r.health_tax, r.pension_employee, r.study_fund_employee, r.net,
        r.delta_net, r.delta_display, r.break_even_participation,
    }
    if r.break_even_participation is not None:
        values.add(math.floor(r.break_even_participation))
    values |= {t.amount for t in r.trace}
    values |= {s.amount for s in r.waterfall}
    if r.national_insurance is not None and r.health_tax is not None:
        values.add(r.national_insurance + r.health_tax)
    values |= set(numbers_in(r.explanation)) | set(numbers_in(r.eligibility.reason_text))
    return {abs(v) for v in values if v is not None}


def allowed_numbers(
    record: ConversationRecord, rules: Rules, comparisons: list[CompareResponse], history: list[dict] | None = None
) -> set[float]:
    allowed: set[float] = set()
    p = record.state.profile
    for name in ("base_salary", "commissions", "bonus", "pension_pct", "study_fund_pct", "credit_points", "children_under_23"):
        value = getattr(p, name).value
        if value is not None:
            allowed.add(float(value))
    current = p.current_option.value
    if current is not None and current.participation is not None and current.participation.value is not None:
        allowed.add(float(current.participation.value))
    for t in record.participations.values():
        if t.value is not None:
            allowed.add(float(t.value))
    for comparison in comparisons:
        for r in [comparison.current, *comparison.alternatives]:
            allowed |= _result_numbers(r)
    allowed |= set(rules.budgets.values())
    allowed |= {rules.electric.net_bonus, rules.family_track.min_children, rules.family_track.child_max_age}
    allowed |= {rules.family_track.gap_split_employee * 100}
    allowed |= tool_output_numbers(history or record.history)
    for m in record.state.messages:  # מה שהעובד והמערכת כתבו
        if m.role in ("user", "system"):
            allowed |= set(numbers_in(m.text))
    return allowed


def check(text: str, allowed: set[float]) -> list[float]:
    """מחזיר את המספרים שאין להם מקור. רשימה ריקה = התשובה עברה."""
    unbacked = []
    for value, kind in tokens(text):
        tolerance = PCT_TOLERANCE if kind == "percent" else MONEY_TOLERANCE
        if any(abs(value - a) <= tolerance for a in allowed):
            continue
        if kind == "bare" and (value <= SMALL and value == int(value) or int(value) in YEARS and value == int(value)):
            continue
        unbacked.append(value)
    return unbacked
