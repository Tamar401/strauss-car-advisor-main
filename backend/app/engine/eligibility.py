"""בדיקת זכאות לחלופה. לא מנחשת: אם חסר נתון שנדרש להחלטה — מחזירה אותו ב-missing."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts import Eligibility
from app.engine.rules import Rules

FAMILY_GROUP = "משפחתי"


@dataclass
class EligibilityResult:
    eligibility: Eligibility | None  # None = אי אפשר להחליט, ראו missing
    missing: list[str] = field(default_factory=list)
    family_track: bool = False
    maintenance: float = 0


def _ok(code, text, **kw):
    return EligibilityResult(Eligibility(eligible=True, reason_code=code, reason_text=text), **kw)


def _no(code, text):
    return EligibilityResult(Eligibility(eligible=False, reason_code=code, reason_text=text))


def check_car(car: dict, group: str | None, children: int | None, rules: Rules) -> EligibilityResult:
    if group is None:
        return EligibilityResult(None, missing=["group"])

    if car["group"] == FAMILY_GROUP or car["id"] in rules.family_track.cars:
        if children is None:
            return EligibilityResult(None, missing=["children_under_23"])
        need = rules.family_track.min_children
        age = rules.family_track.child_max_age
        if children >= need:
            return _ok(
                "family_track",
                f"מסלול ברוכת ילדים ({children} ילדים עד גיל {age}). על הפער מעל תקציב הקבוצה שלך — "
                f"{rules.family_track.gap_split_employee:.0%} עליך",
                family_track=True,
            )
        return _no(
            "family_track_not_eligible",
            f"המסלול המשפחתי מיועד למי שיש לו {need} ילדים ומעלה עד גיל {age}; רשומים לך {children}",
        )

    car_rank, own_rank = rules.group_rank(car["group"]), rules.group_rank(group)
    if car_rank <= own_rank:
        where = "מהקבוצה שלך" if car_rank == own_rank else "מקבוצה נמוכה משלך"
        return _ok("own_group_or_lower", f"הרכב {where} ({car['group']}), ואת/ה בקבוצה {group}")
    return _no(
        "higher_group",
        f"הרכב מקבוצה {car['group']}, גבוהה מהקבוצה שלך ({group}). אפשר לבחור רק מהקבוצה שלך או מקבוצה נמוכה יותר",
    )


def check_waiver(occupation: dict | None) -> EligibilityResult:
    if occupation is None:
        return EligibilityResult(None, missing=["occupation"])
    name = occupation["name"]
    if occupation["car_required"] or not occupation["waiver_allowed"]:
        return _no("waiver_not_allowed", f"בעיסוק שלך ({name}) הרכב הוא חלק מהתפקיד, ולכן אי אפשר לוותר עליו")
    maintenance = occupation["waiver_maintenance"]
    return _ok(
        "waiver_allowed",
        f"העיסוק שלך ({name}) מאפשר ויתור על רכב, ובמקומו אחזקת רכב של {maintenance:,.0f} ₪ (חייבת במס, לא פנסיונית)",
        maintenance=maintenance,
    )
