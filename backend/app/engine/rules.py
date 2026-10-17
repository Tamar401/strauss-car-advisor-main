"""קובץ הכללים כמודל טיפוסי. קובץ לא תקין נכשל בטעינה — לא באמצע חישוב.

השמות בקובץ ב-camelCase (כמו שהגיע מהאתגר); בקוד ב-snake_case.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from app import seed


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class Electric(_Model):
    net_bonus: float = Field(gt=0)
    method: Literal["gross_up", "gross"]


class FamilyTrack(_Model):
    min_children: int = Field(gt=0)
    child_max_age: int
    cars: list[str]
    gap_split_employee: float = Field(ge=0, le=1)


class Waiver(_Model):
    allowed_by: Literal["occupation"]
    maintenance_is_taxable: bool
    maintenance_is_pensionable: bool


class TwoTier(_Model):
    """ביטוח לאומי / בריאות: שיעור מופחת עד הסף, שיעור מלא עד התקרה."""

    threshold: float
    ceiling: float
    low_rate: float
    high_rate: float

    def amount(self, income: float) -> float:
        capped = min(income, self.ceiling)
        return min(capped, self.threshold) * self.low_rate + max(0.0, capped - self.threshold) * self.high_rate


class PensionCredit(_Model):
    rate: float
    max_contribution_rate: float
    income_ceiling: float

    @property
    def max_credited_contribution(self) -> float:
        return self.max_contribution_rate * self.income_ceiling


class NetMethod(_Model):
    tax_year: int
    credit_point_value: float
    brackets: list[tuple[Optional[float], float]]
    national_insurance: TwoTier
    health: TwoTier
    pension_credit: PensionCredit

    @model_validator(mode="after")
    def _brackets_ascending(self):
        caps = [cap for cap, _ in self.brackets]
        if caps[-1] is not None or any(c is None for c in caps[:-1]):
            raise ValueError("מדרגות המס: רק המדרגה האחרונה בלי תקרה (null)")
        if caps[:-1] != sorted(caps[:-1]):
            raise ValueError("מדרגות המס חייבות להיות בסדר עולה")
        return self

    def bracket_tax(self, income: float) -> float:
        tax, floor = 0.0, 0.0
        for cap, rate in self.brackets:
            top = income if cap is None else min(income, cap)
            if top > floor:
                tax += (top - floor) * rate
            if cap is None or income <= cap:
                break
            floor = cap
        return tax


class ValueOfUse(_Model):
    source: str
    drive_field: dict[str, str]  # קוד הנעה במאגר → שם


class Rules(_Model):
    version: str
    budgets: dict[str, float]
    group_order: list[str]
    choose_from: Literal["own_group_or_lower"]
    electric: Electric
    family_track: FamilyTrack
    waiver: Waiver
    unused_budget: Literal["not_paid"]
    net_method: NetMethod
    value_of_use: ValueOfUse

    @model_validator(mode="after")
    def _groups_have_budgets(self):
        missing = set(self.group_order) - set(self.budgets)
        if missing:
            raise ValueError(f"חסר תקציב לקבוצות: {sorted(missing)}")
        return self

    def group_rank(self, group: str) -> int:
        return self.group_order.index(group)


def load_rules(path: Path | None = None) -> Rules:
    path = path or seed.RULES_PATH  # נקרא בכל קריאה — כך שינוי בקובץ (או בבדיקות) נכנס לתוקף מיד
    return Rules.model_validate(json.loads(path.read_text(encoding="utf-8")))
