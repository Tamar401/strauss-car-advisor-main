"""חישוב נטו חודשי לפי netMethod בקובץ הכללים. דטרמיניסטי, ללא עיגול, ומחזיר trace לכל שורה.

הנחות (מתוך קובץ הכללים):
- פנסיה וקרן השתלמות של העובד מחושבות על בסיס + עמלות + בונוס (לא על אחזקה / החזר חשמל).
- שווי שימוש מתווסף להכנסה החייבת במס ולביטוח לאומי ובריאות.
- השתתפות ברכב וחלק העובד במסלול המשפחתי יורדים מהנטו בלבד.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts import TraceLine
from app.engine.rules import Rules

RULES_FILE = "strauss-rules.json"


def _n(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class NetInput:
    base_salary: float
    commissions: float
    bonus: float
    pension_pct: float
    study_fund_pct: float
    credit_points: float
    value_of_use: float = 0
    maintenance: float = 0
    electric_bonus_gross: float = 0
    participation: float = 0
    family_gap_employee: float = 0


@dataclass
class NetResult:
    gross: float
    taxable_income: float
    bracket_tax: float
    credit_points_amount: float
    pension_credit: float
    income_tax: float
    national_insurance: float
    health_tax: float
    pension_employee: float
    study_fund_employee: float
    net: float
    trace: list[TraceLine] = field(default_factory=list)


def compute_net(inp: NetInput, rules: Rules, sources: dict[str, str] | None = None) -> NetResult:
    """sources: מאיפה הגיע כל קלט (למשל value_of_use → 'רשות המסים · 2026/2025/1/01014/00003')."""
    m = rules.net_method
    sources = sources or {}

    contributions_base = inp.base_salary + inp.commissions + inp.bonus
    gross = contributions_base + inp.maintenance + inp.electric_bonus_gross
    taxable = gross + inp.value_of_use

    pension = contributions_base * inp.pension_pct / 100
    study_fund = contributions_base * inp.study_fund_pct / 100

    bracket_tax = m.bracket_tax(taxable)
    credit_points_amount = inp.credit_points * m.credit_point_value
    pension_credit = m.pension_credit.rate * min(pension, m.pension_credit.max_credited_contribution)
    income_tax = max(0.0, bracket_tax - credit_points_amount - pension_credit)

    ni = m.national_insurance.amount(taxable)
    health = m.health.amount(taxable)

    net = gross - income_tax - ni - health - pension - study_fund - inp.participation - inp.family_gap_employee

    def line(key, label, amount, formula=None, source=None):
        return TraceLine(key=key, label=label, amount=amount, formula=formula, source=source)

    ni_r, h_r = m.national_insurance, m.health
    trace = [line("base_salary", "שכר בסיס", inp.base_salary, source=sources.get("base_salary"))]
    if inp.commissions:
        trace.append(line("commissions", "עמלות", inp.commissions, source=sources.get("commissions")))
    if inp.bonus:
        trace.append(line("bonus", "בונוס", inp.bonus, source=sources.get("bonus")))
    if inp.maintenance:
        trace.append(line("maintenance", "אחזקת רכב", inp.maintenance, "חייבת במס, לא פנסיונית", sources.get("maintenance")))
    if inp.electric_bonus_gross:
        formula = (
            f"מגולם: הסכום שמוסיף בדיוק {_n(rules.electric.net_bonus)} ₪ לנטו"
            if rules.electric.method == "gross_up"
            else f"{_n(rules.electric.net_bonus)} ₪ ברוטו"
        )
        trace.append(line("electric_bonus_gross", "החזר חשמל (ברוטו)", inp.electric_bonus_gross, formula, f"{RULES_FILE} · electric"))
    trace += [
        line("gross", "ברוטו", gross),
        line("value_of_use", "שווי שימוש", inp.value_of_use, "מתווסף להכנסה החייבת, לא משולם", sources.get("value_of_use")),
        line("taxable_income", "הכנסה חייבת", taxable, f"ברוטו {_n(gross)} + שווי שימוש {_n(inp.value_of_use)}"),
        line("bracket_tax", "מס לפי מדרגות", bracket_tax, f"מדרגות {m.tax_year} על {_n(taxable)} ₪", f"{RULES_FILE} · netMethod.brackets"),
        line(
            "credit_points",
            "זיכוי נקודות",
            credit_points_amount,
            f"{_n(inp.credit_points)} נקודות × {_n(m.credit_point_value)} ₪",
            sources.get("credit_points"),
        ),
        line(
            "pension_credit",
            "זיכוי פנסיה",
            pension_credit,
            f"{_n(m.pension_credit.rate * 100)}% מהנמוך מבין ההפרשה ({_n(pension)} ₪) לתקרה ({_n(m.pension_credit.max_credited_contribution)} ₪)",
            f"{RULES_FILE} · netMethod.pensionCredit",
        ),
        line("income_tax", "מס הכנסה", income_tax, "מס לפי מדרגות פחות זיכויים (לא פחות מ-0)"),
        line(
            "national_insurance",
            "ביטוח לאומי",
            ni,
            f"{_n(ni_r.low_rate * 100)}% עד {_n(ni_r.threshold)} ₪, {_n(ni_r.high_rate * 100)}% מעל",
            f"{RULES_FILE} · netMethod.nationalInsurance",
        ),
        line(
            "health_tax",
            "מס בריאות",
            health,
            f"{_n(h_r.low_rate * 100)}% עד {_n(h_r.threshold)} ₪, {_n(h_r.high_rate * 100)}% מעל",
            f"{RULES_FILE} · netMethod.health",
        ),
        line("pension_employee", "פנסיה עובד", pension, f"{_n(inp.pension_pct)}% × {_n(contributions_base)}", sources.get("pension_pct")),
        line(
            "study_fund_employee",
            "קרן השתלמות עובד",
            study_fund,
            f"{_n(inp.study_fund_pct)}% × {_n(contributions_base)}",
            sources.get("study_fund_pct"),
        ),
        line("participation", "השתתפות ברכב", inp.participation, "ניכוי מהנטו", sources.get("participation")),
    ]
    if inp.family_gap_employee:
        trace.append(line("family_gap_employee", "חלק העובד במסלול המשפחתי", inp.family_gap_employee, sources.get("family_gap_formula"), f"{RULES_FILE} · familyTrack"))
    trace.append(line("net", "נטו משוער", net))

    return NetResult(
        gross=gross,
        taxable_income=taxable,
        bracket_tax=bracket_tax,
        credit_points_amount=credit_points_amount,
        pension_credit=pension_credit,
        income_tax=income_tax,
        national_insurance=ni,
        health_tax=health,
        pension_employee=pension,
        study_fund_employee=study_fund,
        net=net,
        trace=trace,
    )


def electric_bonus_gross(inp: NetInput, rules: Rules) -> float:
    """כמה ברוטו צריך להוסיף כדי שהנטו יעלה בדיוק ב-netBonus. החיפוש בינארי ומדויק עד שבר אגורה."""
    target = rules.electric.net_bonus
    if rules.electric.method == "gross":
        return target
    base_net = compute_net(inp, rules).net
    lo, hi = target, target * 4
    for _ in range(200):
        mid = (lo + hi) / 2
        gained = compute_net(_with(inp, electric_bonus_gross=mid), rules).net - base_net
        if gained < target:
            lo = mid
        else:
            hi = mid
    return hi


def _with(inp: NetInput, **changes) -> NetInput:
    return NetInput(**{**inp.__dict__, **changes})
