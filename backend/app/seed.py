"""קריאת קבצי ה-seed והכללים. נתיבים מרוכזים כאן כדי שכל השאר לא ינחש איפה הקבצים."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "seed"
RULES_PATH = ROOT / "config" / "strauss-rules.json"
VOU_CSV = ROOT / "data" / "raw" / "vou_2026.csv"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def catalog() -> list[dict]:
    return _load(SEED / "catalog.json")


@lru_cache
def occupations() -> list[dict]:
    return _load(SEED / "occupations.json")


@lru_cache
def employees() -> list[dict]:
    return _load(SEED / "employees.json")


@lru_cache
def golden() -> list[dict]:
    return _load(SEED / "golden.json")


def rules() -> dict:
    # בלי cache — כדי ששינוי בקובץ ייכנס לתוקף בלי להפעיל מחדש
    return _load(RULES_PATH)
