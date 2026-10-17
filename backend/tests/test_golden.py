"""בדיקות הזהב: 6 העובדים לדוגמה, דרך המנוע המלא (זכאות + מאגר + נטו), מול גיליון 'חישובים' באקסל.

השוואה אחרי עיגול לשקל — כמו בתצוגה. החישוב עצמו ללא עיגול.
"""
import pytest

from app import seed
from app.contracts import CompareRequest, OptionRequest
from app.engine.compare import compare, demo_profile

GOLDEN = {g["employee_id"]: g for g in seed.golden()}
EMPLOYEES = {e["id"]: e for e in seed.employees()}


def _alternative(golden_row) -> OptionRequest:
    text = golden_row["alternative"]
    if text.startswith("ויתור"):
        return OptionRequest(kind="waiver")
    model = text.rsplit(" (", 1)[0]
    car = next(c for c in seed.catalog() if c["model"] == model)
    return OptionRequest(kind="car", car_id=car["id"])


@pytest.fixture(scope="module", params=sorted(GOLDEN))
def case(request):
    golden = GOLDEN[request.param]
    req = CompareRequest(profile=demo_profile(EMPLOYEES[request.param]), alternatives=[_alternative(golden)])
    resp = compare(req)
    return golden, resp.current, resp.alternatives[0]


def test_status_and_eligibility(case):
    golden, current, alt = case
    assert current.status == "complete"
    assert alt.status == "complete"
    assert alt.eligibility.eligible == golden["eligible"]


def test_net(case):
    golden, current, alt = case
    assert round(current.net) == golden["net_today"]
    assert round(alt.net) == golden["net_alternative"]
    assert alt.delta_display == golden["delta"]
    assert alt.delta_display == round(alt.net) - round(current.net)


def test_tax_and_social(case):
    golden, current, alt = case
    assert round(current.income_tax) == golden["tax_today"]
    assert round(alt.income_tax) == golden["tax_alternative"]
    assert round(current.national_insurance + current.health_tax) == golden["ni_health_today"]
    assert round(alt.national_insurance + alt.health_tax) == golden["ni_health_alternative"]


def test_electric_and_family(case):
    golden, current, alt = case
    assert round(alt.electric_bonus_gross) == golden["electric_gross"]
    assert round(alt.family_gap_employee) == golden["family_gap_employee"]


def test_waterfall_sums_to_delta(case):
    _, _, alt = case
    assert sum(s.amount for s in alt.waterfall) == pytest.approx(alt.delta_net, abs=1e-6)


def test_trace_net_matches(case):
    _, current, alt = case
    for r in (current, alt):
        assert next(t for t in r.trace if t.key == "net").amount == r.net
