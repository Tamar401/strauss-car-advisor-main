"""תרחישי קצה: זכאות, מידע חסר, דטרמיניזם, מאגר שווי השימוש וולידציית הכללים."""
import json

import pytest
from pydantic import ValidationError

from app import seed
from app.contracts import CompareRequest, OptionRequest, Tracked, VouKey
from app.engine import vou
from app.engine.compare import compare, compare_all, demo_profile
from app.engine.rules import Rules, load_rules

EMPLOYEES = {e["id"]: e for e in seed.employees()}


def profile(employee_id="E-001", **changes):
    p = demo_profile(EMPLOYEES[employee_id])
    for field, value in changes.items():
        setattr(p, field, value)
    return p


def run(p, *alternatives):
    return compare(CompareRequest(profile=p, alternatives=list(alternatives)))


def car(car_id, participation=None):
    return OptionRequest(kind="car", car_id=car_id, participation=participation)


WAIVER = OptionRequest(kind="waiver")


# ---------- זכאות ----------


def test_group_b_employee_can_waive():
    """מופיע במפורש בטיפים של האתגר: עובדת מקבוצה ב שרוצה לוותר על הרכב."""
    p = profile(
        "E-001",
        occupation=Tracked(value="אנליסט/ית נתונים", source="employee"),
        current_option=Tracked(value=car("CAR-05", Tracked(value=250, source="employee")), source="employee"),
    )
    alt = run(p, WAIVER).alternatives[0]
    assert alt.status == "complete"
    assert alt.eligibility.reason_code == "waiver_allowed"
    assert alt.maintenance == 1500
    assert alt.value_of_use == 0
    assert alt.employee_participation == 0


def test_field_role_cannot_waive():
    alt = run(profile("E-002"), WAIVER).alternatives[0]
    assert alt.status == "blocked"
    assert alt.eligibility.reason_code == "waiver_not_allowed"
    assert alt.net is None


def test_higher_group_is_blocked():
    alt = run(profile("E-001"), car("CAR-14")).alternatives[0]  # טסלה, קבוצה ד; העובדת בקבוצה ג
    assert alt.status == "blocked"
    assert alt.eligibility.reason_code == "higher_group"


def test_lower_group_is_allowed():
    alt = run(profile("E-006"), car("CAR-01")).alternatives[0]  # עובד קבוצה ד בוחר מקבוצה א
    assert alt.status == "complete"
    assert alt.eligibility.reason_code == "own_group_or_lower"


def test_family_track_requires_enough_children():
    p = profile("E-004")  # 3 ילדים
    alt = run(p, car("CAR-19")).alternatives[0]
    assert alt.status == "blocked"
    assert alt.eligibility.reason_code == "family_track_not_eligible"


def test_family_track_gap_uses_own_group_budget():
    alt = run(profile("E-006"), car("CAR-20")).alternatives[0]  # 4 ילדים, קבוצה ד (5,200), סנטה פה 5,600
    assert alt.eligibility.reason_code == "family_track"
    assert alt.family_gap_employee == pytest.approx((5600 - 5200) * 0.5)


def test_occupation_table_decides_the_group():
    """העובדת אמרה 'קבוצה ד', אבל לפי טבלת העיסוקים מנהל/ת מוצר בקבוצה ג — הטבלה קובעת."""
    p = profile("E-001", group=Tracked(value="ד", source="employee"))
    alt = run(p, car("CAR-14")).alternatives[0]
    assert alt.status == "blocked"
    assert alt.budget == 4500


# ---------- מידע חסר: לא מנחשים ----------


def test_missing_participation_is_partial_not_guessed():
    alt = run(profile("E-001"), car("CAR-10", Tracked(source="missing"))).alternatives[0]
    assert alt.status == "partial"
    assert alt.missing == ["participation"]
    assert alt.net is None and alt.delta_net is None
    assert "נציג" in alt.explanation


def test_participation_defaults_to_catalog_when_not_specified():
    alt = run(profile("E-001"), car("CAR-10")).alternatives[0]
    assert alt.employee_participation == 300
    assert next(t for t in alt.trace if t.key == "participation").source == "קטלוג (ברירת מחדל)"


def test_rep_answer_is_used_and_attributed():
    alt = run(profile("E-001"), car("CAR-10", Tracked(value=350, source="rep", note="בתוקף מ-1/1"))).alternatives[0]
    assert alt.employee_participation == 350
    assert next(t for t in alt.trace if t.key == "participation").source == "נציג התחבורה"


def test_missing_salary_blocks_all_numbers():
    resp = run(profile("E-001", credit_points=Tracked(source="missing")), car("CAR-10"))
    assert resp.current.status == "partial"
    assert "credit_points" in resp.current.missing
    assert resp.alternatives[0].status == "partial"
    assert resp.current.net is None


def test_missing_group_and_occupation():
    p = profile("E-001", occupation=Tracked(source="missing"), group=Tracked(source="missing"))
    alt = run(p, car("CAR-10")).alternatives[0]
    assert alt.status == "partial"
    assert "group" in alt.missing


def test_unknown_current_situation():
    resp = run(profile("E-001", current_option=Tracked(source="missing")), car("CAR-10"))
    assert resp.current.missing == ["current_option"]
    assert resp.alternatives[0].delta_net is None


# ---------- דטרמיניזם וחשמל ----------


def test_same_input_same_output():
    a = run(profile("E-004"), car("CAR-11"), WAIVER).model_dump_json()
    b = run(profile("E-004"), car("CAR-11"), WAIVER).model_dump_json()
    assert a == b


def test_electric_gross_up_adds_exactly_net_bonus():
    """אותו רכב, פעם עם החזר מגולם ופעם בלי: ההפרש בנטו הוא בדיוק 250."""
    rules = load_rules()
    with_bonus = run(profile("E-001"), car("CAR-10")).alternatives[0]
    no_bonus_rules = rules.model_copy(deep=True)
    no_bonus_rules.electric.net_bonus = 1e-9
    without = compare(CompareRequest(profile=profile("E-001"), alternatives=[car("CAR-10")]), no_bonus_rules).alternatives[0]
    assert with_bonus.net - without.net == pytest.approx(250, abs=1e-6)


def test_simple_gross_method_from_rules():
    rules = load_rules().model_copy(deep=True)
    rules.electric.method = "gross"
    alt = compare(CompareRequest(profile=profile("E-001"), alternatives=[car("CAR-10")]), rules).alternatives[0]
    assert alt.electric_bonus_gross == 250


# ---------- השוואה מול כל החלופות ----------


def test_compare_all_sorted_and_excludes_current():
    resp = compare_all(profile("E-001"))
    ids = [a.option.car_id for a in resp.alternatives]
    assert "CAR-09" not in ids  # הרכב של היום
    statuses = [a.status for a in resp.alternatives]
    assert statuses == sorted(statuses, key=["complete", "partial", "blocked"].index)
    deltas = [a.delta_net for a in resp.alternatives if a.status == "complete"]
    assert deltas == sorted(deltas, reverse=True)


# ---------- מאגר שווי השימוש ----------


def test_full_key_distinguishes_atto3_from_tang():
    base = dict(tax_year=2026, registration_year=2025, manufacturer_code="01014", model_code="00003")
    assert vou.lookup(VouKey(vehicle_type_code=1, **base))["commercial_name"] == "ATTO 3"
    assert vou.lookup(VouKey(vehicle_type_code=2, **base))["commercial_name"] == "TANG"


@pytest.mark.parametrize("c", seed.catalog(), ids=lambda c: c["id"])
def test_every_catalog_car_resolves_to_its_value_of_use(c):
    key = vou.resolve_catalog_car(c["registration_year"], c["manufacturer_code"], c["model_code"], c["model_description"])
    assert vou.lookup(key)["value_of_use"] == c["value_of_use"]


def test_ambiguous_resolution_refuses():
    with pytest.raises(LookupError):
        vou.resolve_catalog_car(2025, "01014", "00003", "NO-SUCH-DESCRIPTION")


# ---------- ולידציית קובץ הכללים ----------


def _raw_rules():
    return json.loads(seed.RULES_PATH.read_text(encoding="utf-8"))


def test_rules_file_is_valid():
    assert load_rules().budgets["ג"] == 4500


def test_rules_reject_missing_budget():
    raw = _raw_rules()
    del raw["budgets"]["ד"]
    with pytest.raises(ValidationError):
        Rules.model_validate(raw)


def test_rules_reject_unsorted_brackets():
    raw = _raw_rules()
    raw["netMethod"]["brackets"][0][0] = 99999
    with pytest.raises(ValidationError):
        Rules.model_validate(raw)


def test_budget_change_in_rules_changes_result_without_code_change():
    rules = load_rules().model_copy(deep=True)
    rules.budgets["ד"] = 6000
    alt = compare(CompareRequest(profile=profile("E-006"), alternatives=[car("CAR-20")]), rules).alternatives[0]
    assert alt.family_gap_employee == 0  # התקציב החדש מכסה את הסנטה פה
