"""נקודת האיזון: כשההשתתפות ברכב החדש לא ידועה, המנוע עדיין עונה — עד איזו השתתפות הרכב משתלם."""
import math

import pytest

from app import seed
from app.contracts import CompareRequest, OptionRequest, Tracked
from app.engine.compare import compare, demo_profile

EMPLOYEES = {e["id"]: e for e in seed.employees()}


def run(employee_id, car_id, participation):
    profile = demo_profile(EMPLOYEES[employee_id])
    option = OptionRequest(kind="car", car_id=car_id, participation=participation)
    resp = compare(CompareRequest(profile=profile, alternatives=[option]))
    return resp.current, resp.alternatives[0]


@pytest.mark.parametrize("employee_id", sorted(EMPLOYEES))
@pytest.mark.parametrize("car_id", ["CAR-06", "CAR-10"])
def test_break_even_is_exact(employee_id, car_id):
    """השתתפות בגובה נקודת האיזון מחזירה בדיוק את הנטו של היום — זה גבול מחושב, לא הערכה."""
    _, partial = run(employee_id, car_id, Tracked(source="missing"))
    if partial.status == "blocked":
        pytest.skip("הרכב לא זמין לעובד הזה")
    assert partial.status == "partial" and partial.missing == ["participation"]
    assert partial.net is None  # עדיין לא ממציאים נטו בלי ההשתתפות
    b = partial.break_even_participation
    assert b is not None

    _, at_b = run(employee_id, car_id, Tracked(value=b, source="employee"))
    assert at_b.delta_net == pytest.approx(0, abs=1e-6)
    if b > 1:
        _, below = run(employee_id, car_id, Tracked(value=b - 1, source="employee"))
        assert below.delta_net == pytest.approx(1, abs=1e-6)  # כל שקל השתתפות הוא שקל נטו


def test_complete_option_reports_its_margin():
    # נועה (E-001): ATTO 3 בהשתתפות 300 ₪ מעלה את הנטו ב-661 ₪ (נטו הייחוס)
    _, alt = run("E-001", "CAR-10", Tracked(value=300, source="employee"))
    assert alt.delta_display == 661
    assert alt.break_even_participation == pytest.approx(alt.delta_net + 300)


def test_waiting_for_rep_explanation_gives_the_threshold():
    _, alt = run("E-001", "CAR-10", Tracked(source="missing"))
    assert "שאלתי את נציג התחבורה" in alt.explanation
    assert f"{math.floor(alt.break_even_participation):,}" in alt.explanation
    assert "משתלם לך כל עוד" in alt.explanation


def test_negative_break_even_says_no_participation_helps():
    # E-003 מוותר היום על הרכב: כל רכב מוסיף שווי שימוש חייב במס
    _, alt = run("E-003", "CAR-06", Tracked(source="missing"))
    assert alt.break_even_participation < 0
    assert "גם בלי השתתפות בכלל" in alt.explanation


def test_no_break_even_for_waiver():
    profile = demo_profile(EMPLOYEES["E-001"])
    resp = compare(CompareRequest(profile=profile, alternatives=[OptionRequest(kind="waiver")]))
    assert resp.alternatives[0].break_even_participation is None
