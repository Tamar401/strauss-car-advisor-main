"""בדיקות שה-API, החוזה וה-seed מסונכרנים. אם נשבר כאן — מישהי שינתה חוזה בלי לעדכן."""
from fastapi.testclient import TestClient

from app import seed
from app.contracts import Car, CompareResponse, Occupation
from app.main import app

client = TestClient(app)


def test_seed_matches_contracts():
    assert len(seed.catalog()) == 20
    assert len(seed.occupations()) == 14
    for c in seed.catalog():
        Car.model_validate(c)
    for o in seed.occupations():
        Occupation.model_validate(o)


def test_demo_compare_endpoint():
    resp = CompareResponse.model_validate(client.get("/api/demo/compare/E-001").json())
    golden = next(g for g in seed.golden() if g["employee_id"] == "E-001")
    atto3 = next(a for a in resp.alternatives if a.option.car_id == "CAR-10")
    assert round(resp.current.net) == golden["net_today"]
    assert atto3.delta_display == golden["delta"]


def test_compare_endpoint_rejects_unknown_car():
    employee = client.get("/api/demo-employees").json()[0]
    assert "national_id" not in employee
    body = {"profile": {}, "alternatives": [{"kind": "car", "car_id": "CAR-99"}]}
    assert client.post("/api/compare", json=body).status_code == 400
