"""מנוע ההשוואה: פרופיל עובד + חלופות → CompareResponse.

כאן נאכף "לא מנחשים": כל נתון חסר מסומן ב-missing, והחלופה מקבלת status='partial' בלי מספרים.
אותם נתונים + אותם כללים = אותה תוצאה, תמיד.
"""
from __future__ import annotations

from app import seed
from app.contracts import (
    CompareRequest,
    CompareResponse,
    Eligibility,
    EmployeeProfile,
    OptionRequest,
    OptionResult,
    Tracked,
    WaterfallStep,
)
from app.engine import vou
from app.engine.eligibility import EligibilityResult, check_car, check_waiver
from app.engine.net import NetInput, NetResult, compute_net, electric_bonus_gross
from app.engine.rules import Rules, load_rules

SALARY_FIELDS = ["base_salary", "commissions", "bonus", "pension_pct", "study_fund_pct", "credit_points"]

FIELD_NAMES = {
    "group": "קבוצת הזכאות",
    "occupation": "העיסוק",
    "base_salary": "שכר הבסיס",
    "commissions": "העמלות",
    "bonus": "הבונוס",
    "pension_pct": "אחוז ההפרשה לפנסיה",
    "study_fund_pct": "אחוז ההפרשה לקרן השתלמות",
    "credit_points": "נקודות הזיכוי",
    "children_under_23": "מספר הילדים עד גיל 23",
    "current_option": "הרכב (או הוויתור) שיש לך היום",
    "current_vehicle": "איזה רכב בדיוק יש לך היום (רמת הגימור)",
    "participation": "סכום ההשתתפות שלך ברכב",
}

DRIVE_KEYS = {"בנזין": "petrol", "היברידי": "hybrid", "פלאג-אין": "plugin", "חשמלי": "electric"}
DRIVE_LABELS = {v: k for k, v in DRIVE_KEYS.items()}

SOURCE_LABELS = {
    "employee": "העובד",
    "payslip": "תלוש (אושר ע״י העובד)",
    "rep": "נציג התחבורה",
    "catalog": "קטלוג (ברירת מחדל)",
    "rules": "טבלת העיסוקים",
}


def _value(t: Tracked | None):
    if t is None or t.source == "missing" or t.value is None:
        return None
    return t.value


def _source(t: Tracked | None) -> str | None:
    return SOURCE_LABELS.get(t.source) if t else None


def _f(x: float) -> str:
    return f"{x:,.0f}"


class _Context:
    """מה שמשותף לכל החלופות של אותו עובד."""

    def __init__(self, profile: EmployeeProfile, rules: Rules):
        self.rules = rules
        self.profile = profile
        self.catalog = {c["id"]: c for c in seed.catalog()}
        occupations = {o["name"]: o for o in seed.occupations()}

        occ_name = _value(profile.occupation)
        self.occupation = occupations.get(occ_name) if occ_name else None
        # הקבוצה נקבעת לפי טבלת העיסוקים כשהעיסוק ידוע — לא לפי מה שהעובד זוכר
        self.group = self.occupation["group"] if self.occupation else _value(profile.group)
        self.children = _value(profile.children_under_23)
        self.salary = {f: _value(getattr(profile, f)) for f in SALARY_FIELDS}
        self.missing_salary = [f for f, v in self.salary.items() if v is None]
        self.sources = {f: _source(getattr(profile, f)) for f in SALARY_FIELDS}

    @property
    def budget(self) -> float:
        return self.rules.budgets.get(self.group, 0) if self.group else 0


def _car_details(car: dict, rules: Rules):
    key = vou.resolve_catalog_car(car["registration_year"], car["manufacturer_code"], car["model_code"], car["model_description"])
    record = vou.lookup(key)
    drive = DRIVE_KEYS[rules.value_of_use.drive_field[str(record["drive_code"])]]
    return record["value_of_use"], drive, f"רשות המסים · מפתח {vou.key_text(key)}"


def _evaluate(option: OptionRequest, ctx: _Context, is_current: bool) -> tuple[OptionResult, NetResult | None]:
    rules = ctx.rules
    car = None
    value_of_use = 0.0
    drive = None
    vou_source = None
    participation = 0.0
    participation_source = "ויתור — אין השתתפות"
    missing: list[str] = []

    if option.kind == "waiver":
        elig = check_waiver(ctx.occupation)
        label = "ויתור על הרכב"
        if elig.maintenance:
            label += f" · אחזקת רכב {_f(elig.maintenance)} ₪"
    elif option.car_id is None and option.vou_key is None:
        # יש רכב, אבל עוד לא זוהה במאגר (למשל כמה רמות גימור והעובד לא בטוח) — מחכים לנציג, לא מנחשים
        label = option.vehicle_label or "הרכב של היום (טרם זוהה)"
        elig = EligibilityResult(None, missing=["current_vehicle"])
        missing.append("current_vehicle")
        if _value(option.participation) is not None:
            participation, participation_source = option.participation.value, _source(option.participation)
    elif option.car_id is None and option.vou_key is not None:
        # רכב מחוץ לקטלוג (בדרך כלל הרכב של היום) — מזוהה במאגר לפי המפתח המלא
        record = vou.lookup(option.vou_key)
        if record is None:
            raise ValueError(f"הרכב לא נמצא במאגר רשות המסים: {vou.key_text(option.vou_key)}")
        value_of_use = record["value_of_use"]
        drive = DRIVE_KEYS[rules.value_of_use.drive_field[str(record["drive_code"])]]
        vou_source = f"רשות המסים · מפתח {vou.key_text(option.vou_key)}"
        name = option.vehicle_label or f"{record['commercial_name']} ({record['registration_year']})"
        label = f"{name} · {DRIVE_LABELS[drive]}"
        elig = EligibilityResult(Eligibility(
            eligible=False,
            reason_code="not_in_catalog",
            reason_text="אפשר לבחור רכב חדש רק מקטלוג הרכבים של החברה",
        ))
        if _value(option.participation) is None:
            missing.append("participation")
        else:
            participation, participation_source = option.participation.value, _source(option.participation)
    else:
        car = ctx.catalog.get(option.car_id or "")
        if car is None:
            raise ValueError(f"רכב לא מוכר בקטלוג: {option.car_id}")
        value_of_use, drive, vou_source = _car_details(car, rules)
        label = f"{car['model']} ({car['registration_year']}) · {DRIVE_LABELS[drive]}"
        elig = check_car(car, ctx.group, ctx.children, rules)

        if option.participation is None:
            participation, participation_source = car["default_participation"], SOURCE_LABELS["catalog"]
        elif _value(option.participation) is None:
            missing.append("participation")
        else:
            participation, participation_source = option.participation.value, _source(option.participation)

    if is_current:
        # המצב היום הוא עובדה, לא בקשה — לא בודקים זכאות, רק את ההשלכות (מסלול משפחתי / אחזקה)
        family = bool(car and (car["group"] == "משפחתי" or car["id"] in rules.family_track.cars))
        maintenance = elig.maintenance if option.kind == "waiver" else 0
        if option.kind == "waiver" and elig.eligibility is None:
            missing += elig.missing
        elig = EligibilityResult(
            Eligibility(eligible=True, reason_code="current", reason_text="המצב שלך היום"),
            family_track=family,
            maintenance=maintenance,
        )
    else:
        missing += elig.missing

    missing = list(dict.fromkeys(ctx.missing_salary + missing))
    eligibility = elig.eligibility or Eligibility(
        eligible=False,
        reason_code="higher_group" if option.kind != "waiver" else "waiver_not_allowed",
        reason_text="אי אפשר לבדוק זכאות לפני שיש לי " + ", ".join(FIELD_NAMES[m] for m in missing),
    )

    family_gap = 0.0
    if elig.family_track and car is not None:
        if ctx.group is None:
            missing.append("group")
        else:
            family_gap = max(0.0, car["monthly_cost"] - ctx.budget) * rules.family_track.gap_split_employee

    result = OptionResult(
        option=option,
        label=label,
        status="complete",
        missing=missing,
        eligibility=eligibility,
        car=car,
        drive=drive,
        budget=ctx.budget,
        monthly_cost=car["monthly_cost"] if car else None,
        employee_participation=None if "participation" in missing else participation,
        family_gap_employee=family_gap,
        value_of_use=value_of_use,
        maintenance=elig.maintenance,
        explanation="",
    )

    if elig.eligibility is not None and not eligibility.eligible:
        result.status = "blocked"
        result.missing = []
        return result, None
    if missing:
        result.status = "partial"
        return result, None

    s = ctx.salary
    inp = NetInput(
        base_salary=s["base_salary"],
        commissions=s["commissions"],
        bonus=s["bonus"],
        pension_pct=s["pension_pct"],
        study_fund_pct=s["study_fund_pct"],
        credit_points=s["credit_points"],
        value_of_use=value_of_use,
        maintenance=elig.maintenance,
        participation=participation,
        family_gap_employee=family_gap,
    )
    if drive == "electric":
        inp = NetInput(**{**inp.__dict__, "electric_bonus_gross": electric_bonus_gross(inp, rules)})

    sources = {
        **{k: v for k, v in ctx.sources.items() if v},
        "value_of_use": vou_source or "ללא רכב",
        "participation": participation_source,
        "maintenance": "טבלת העיסוקים",
    }
    if family_gap and car:
        sources["family_gap_formula"] = (
            f"(עלות {_f(car['monthly_cost'])} − תקציב {_f(ctx.budget)}) × {rules.family_track.gap_split_employee:.0%}"
        )
    net = compute_net(inp, rules, sources)

    result.electric_bonus_gross = inp.electric_bonus_gross
    result.gross = net.gross
    result.taxable_income = net.taxable_income
    result.income_tax = net.income_tax
    result.national_insurance = net.national_insurance
    result.health_tax = net.health_tax
    result.pension_employee = net.pension_employee
    result.study_fund_employee = net.study_fund_employee
    result.net = net.net
    result.trace = net.trace
    return result, net


def _waterfall(cur: OptionResult, alt: OptionResult) -> list[WaterfallStep]:
    """פירוק ההפרש. סכום הצעדים = delta_net בדיוק (אותה נוסחת נטו, רכיב אחרי רכיב)."""
    steps = [
        ("electric_bonus", "החזר חשמל (ברוטו)", alt.electric_bonus_gross - cur.electric_bonus_gross),
        ("maintenance", "אחזקת רכב", alt.maintenance - cur.maintenance),
        ("income_tax", "מס הכנסה", cur.income_tax - alt.income_tax),
        (
            "ni_health",
            "ביטוח לאומי ובריאות",
            (cur.national_insurance + cur.health_tax) - (alt.national_insurance + alt.health_tax),
        ),
        (
            "contributions",
            "פנסיה וקרן השתלמות",
            (cur.pension_employee + cur.study_fund_employee) - (alt.pension_employee + alt.study_fund_employee),
        ),
        ("participation", "השתתפות ברכב", cur.employee_participation - alt.employee_participation),
        ("family_gap", "חלק העובד במסלול המשפחתי", cur.family_gap_employee - alt.family_gap_employee),
    ]
    return [WaterfallStep(key=k, label=lbl, amount=a) for k, lbl, a in steps if abs(a) >= 0.005]


def _why(cur: OptionResult, alt: OptionResult, rules: Rules) -> str:
    parts = []
    if cur.value_of_use != alt.value_of_use:
        if not cur.value_of_use:
            parts.append(f"נוסף שווי שימוש של {_f(alt.value_of_use)} ₪")
        elif not alt.value_of_use:
            parts.append(f"בוטל שווי שימוש של {_f(cur.value_of_use)} ₪")
        else:
            direction = "יורד" if alt.value_of_use < cur.value_of_use else "עולה"
            parts.append(f"שווי השימוש {direction} מ-{_f(cur.value_of_use)} ל-{_f(alt.value_of_use)} ₪")
    if alt.electric_bonus_gross and not cur.electric_bonus_gross:
        parts.append(f"נוסף החזר חשמל של {_f(rules.electric.net_bonus)} ₪ נטו")
    elif cur.electric_bonus_gross and not alt.electric_bonus_gross:
        parts.append(f"יורד החזר החשמל ({_f(rules.electric.net_bonus)} ₪ נטו)")
    if alt.maintenance != cur.maintenance:
        if alt.maintenance:
            parts.append(f"נוספת אחזקת רכב של {_f(alt.maintenance)} ₪ (חייבת במס)")
        else:
            parts.append(f"בוטלה אחזקת רכב של {_f(cur.maintenance)} ₪")
    if alt.employee_participation != cur.employee_participation:
        parts.append(f"ההשתתפות שלך משתנה מ-{_f(cur.employee_participation)} ל-{_f(alt.employee_participation)} ₪")
    if alt.family_gap_employee:
        parts.append(f"חלקך בפער של המסלול המשפחתי: {_f(alt.family_gap_employee)} ₪")
    return " · ".join(parts) or "שום רכיב לא משתנה"


def _explain(cur: OptionResult, alt: OptionResult | None, rules: Rules) -> str:
    if alt is None:  # המצב היום
        if cur.status != "complete":
            return _explain_missing(cur)
        line2 = (
            f"שווי השימוש של הרכב ({_f(cur.value_of_use)} ₪) מתווסף להכנסה החייבת במס."
            if cur.value_of_use
            else f"אין רכב, ומתקבלת אחזקת רכב של {_f(cur.maintenance)} ₪ (חייבת במס)."
        )
        return f"זה המצב היום: נטו משוער {_f(cur.net)} ₪.\n{line2}"
    if alt.status == "blocked":
        return f"החלופה הזו לא זמינה לך.\n{alt.eligibility.reason_text}."
    if alt.status == "partial":
        return _explain_missing(alt)
    if cur.status != "complete":
        return f"נטו משוער בחלופה: {_f(alt.net)} ₪.\nכדי להשוות למצב היום חסר לי {_missing_text(cur.missing)}."
    d = alt.delta_display
    line1 = "הנטו כמעט לא משתנה." if d == 0 else f"הנטו {'עולה' if d > 0 else 'יורד'} ב-{_f(abs(d))} ₪ בחודש."
    return f"{line1}\n{_why(cur, alt, rules)}."


def _missing_text(missing: list[str]) -> str:
    return ", ".join(FIELD_NAMES.get(m, m) for m in missing)


def _explain_missing(r: OptionResult) -> str:
    if r.missing == ["participation"]:
        return "חסר לי סכום ההשתתפות שלך ברכב הזה, ושאלתי את נציג התחבורה.\nההשוואה תתעדכן ברגע שתגיע תשובה."
    return f"כדי לחשב חסר לי: {_missing_text(r.missing)}.\nאני לא מנחש — ברגע שהנתון יגיע, החישוב יתעדכן."


def compare(req: CompareRequest, rules: Rules | None = None) -> CompareResponse:
    rules = rules or load_rules()
    ctx = _Context(req.profile, rules)

    current_option = _value(req.profile.current_option)
    if current_option is None:
        current = OptionResult(
            option=OptionRequest(kind="waiver"),
            label="המצב היום — לא ידוע",
            status="partial",
            missing=["current_option"],
            eligibility=Eligibility(eligible=True, reason_code="current", reason_text="המצב שלך היום"),
            budget=ctx.budget,
            explanation="",
        )
    else:
        current, _ = _evaluate(current_option, ctx, is_current=True)
    current.explanation = _explain(current, None, rules)

    alternatives = []
    for option in req.alternatives:
        alt, _ = _evaluate(option, ctx, is_current=False)
        if alt.status == "complete" and current.status == "complete":
            alt.delta_net = alt.net - current.net
            alt.delta_display = round(alt.net) - round(current.net)
            alt.waterfall = _waterfall(current, alt)
        alt.explanation = _explain(current, alt, rules)
        alternatives.append(alt)

    return CompareResponse(rules_version=rules.version, current=current, alternatives=alternatives)


def all_options(profile: EmployeeProfile) -> list[OptionRequest]:
    """כל החלופות האפשריות: כל רכב בקטלוג + ויתור, חוץ מהמצב היום."""
    current = _value(profile.current_option)
    options = [
        OptionRequest(kind="car", car_id=c["id"])
        for c in seed.catalog()
        if not (current and current.kind != "waiver" and current.car_id == c["id"])
    ]
    if not (current and current.kind == "waiver"):
        options.append(OptionRequest(kind="waiver"))
    return options


def compare_all(profile: EmployeeProfile, rules: Rules | None = None) -> CompareResponse:
    """השוואה מול כל החלופות, ממוינת: מחושבות לפי ההפרש (הטוב ראשון), אחריהן חלקיות, ובסוף לא זמינות."""
    resp = compare(CompareRequest(profile=profile, alternatives=all_options(profile)), rules)
    order = {"complete": 0, "partial": 1, "blocked": 2}
    resp.alternatives.sort(key=lambda a: (order[a.status], -(a.delta_net or 0)))
    return resp


def demo_question_option(employee_id: str) -> OptionRequest:
    """החלופה שהעובד לדוגמה שאל עליה (מגיליון 'חישובים'), למשל 'ATTO 3 (2025)' או 'ויתור - אחזקת רכב'."""
    text = next(g for g in seed.golden() if g["employee_id"] == employee_id)["alternative"]
    if text.startswith("ויתור"):
        return OptionRequest(kind="waiver")
    model = text.rsplit(" (", 1)[0]
    return OptionRequest(kind="car", car_id=next(c["id"] for c in seed.catalog() if c["model"] == model))


def demo_profile(employee: dict) -> EmployeeProfile:
    """פרופיל מלא מאחד העובדים לדוגמה — לבדיקות ולכפתור "נתוני דמו"."""

    def t(value):
        return Tracked(value=value, source="employee", confirmed=True)

    cur = employee["current_option"]
    current = OptionRequest(
        kind=cur["kind"],
        car_id=cur.get("car_id"),
        participation=t(employee["current_participation"]) if cur["kind"] != "waiver" else None,
    )
    return EmployeeProfile(
        occupation=t(employee["occupation"]),
        group=t(employee["group"]),
        base_salary=t(employee["base_salary"]),
        commissions=t(employee["commissions"]),
        bonus=t(employee["bonus"]),
        pension_pct=t(employee["pension_pct"]),
        study_fund_pct=t(employee["study_fund_pct"]),
        credit_points=t(employee["credit_points"]),
        children_under_23=t(employee["children_under_23"]),
        current_option=t(current),
    )
