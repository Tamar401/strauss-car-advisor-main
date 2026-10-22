"""החוזים בין השכבות — מקור האמת למבני הנתונים של ה-API.

כל שינוי כאן = שינוי בחוזה בין שתי המפתחות. משנים רק בהסכמה, ומעדכנים את docs/CONTRACTS.md.
כל הסכומים בשקלים, לחודש, ללא עיגול (העיגול רק בתצוגה).
"""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

Group = Literal["א", "ב", "ג", "ד"]
Drive = Literal["petrol", "hybrid", "plugin", "electric"]

# ---------- מקור לכל נתון: "לא מנחשים" נאכף כאן ----------

Source = Literal[
    "employee",  # העובד הקליד
    "payslip",  # חולץ מתלוש — דורש אישור העובד
    "rep",  # נציג התחבורה ענה
    "catalog",  # ברירת מחדל מקטלוג הרכבים
    "rules",  # נגזר מקובץ הכללים / טבלת העיסוקים
    "missing",  # עדיין לא ידוע — המנוע לא ירוץ על שדה כזה
]


class Tracked(BaseModel, Generic[T]):
    """ערך + מאיפה הוא הגיע. value=None רק כש-source='missing'."""

    value: Optional[T] = None
    source: Source = "missing"
    confirmed: bool = False
    note: Optional[str] = None  # למשל "בתוקף מ-1/1" מתשובת הנציג


# ---------- רכב ומפתח שווי שימוש ----------


class VouKey(BaseModel):
    """המפתח הרשמי של רשות המסים. שם מסחרי לבד לא מספיק."""

    tax_year: int
    registration_year: int
    vehicle_type_code: int
    manufacturer_code: str  # עם אפסים מובילים, למשל "01014"
    model_code: str  # עם אפסים מובילים, למשל "00003"


class Car(BaseModel):
    id: str  # CAR-01 .. CAR-20
    group: Literal["א", "ב", "ג", "ד", "משפחתי"]
    manufacturer: str
    manufacturer_code: str
    model: str
    model_code: str
    model_description: str
    registration_year: int
    drive: Drive
    list_price: float
    value_of_use: float
    monthly_cost: float
    default_participation: float


class Occupation(BaseModel):
    name: str
    group: Group
    car_required: bool
    waiver_allowed: bool
    waiver_maintenance: float


# ---------- פרופיל העובד ----------


class OptionRequest(BaseModel):
    """חלופה: רכב מהקטלוג, רכב במסלול המשפחתי, או ויתור על רכב."""

    kind: Literal["car", "family_car", "waiver"]
    car_id: Optional[str] = None  # רכב מהקטלוג
    # רכב מחוץ לקטלוג (בדרך כלל הרכב של היום): מזוהה במאגר רשות המסים לפי המפתח המלא
    vou_key: Optional[VouKey] = None
    vehicle_label: Optional[str] = None  # שם לתצוגה, למשל "טויוטה COROLLA (2021)"
    # השתתפות העובד ברכב. None = לא ידוע → המנוע יחזיר status='partial' וה-missing יכלול אותה
    participation: Optional[Tracked[float]] = None


class EmployeeProfile(BaseModel):
    occupation: Tracked[str] = Field(default_factory=Tracked)
    group: Tracked[Group] = Field(default_factory=Tracked)
    base_salary: Tracked[float] = Field(default_factory=Tracked)
    commissions: Tracked[float] = Field(default_factory=Tracked)
    bonus: Tracked[float] = Field(default_factory=Tracked)
    pension_pct: Tracked[float] = Field(default_factory=Tracked)
    study_fund_pct: Tracked[float] = Field(default_factory=Tracked)
    credit_points: Tracked[float] = Field(default_factory=Tracked)
    children_under_23: Tracked[int] = Field(default_factory=Tracked)
    current_option: Tracked[OptionRequest] = Field(default_factory=Tracked)


# ---------- השוואה: POST /api/compare ----------


class CompareRequest(BaseModel):
    profile: EmployeeProfile
    alternatives: list[OptionRequest]


class Eligibility(BaseModel):
    eligible: bool
    reason_code: Literal[
        "own_group_or_lower",
        "higher_group",
        "family_track",
        "family_track_not_eligible",
        "waiver_allowed",
        "waiver_not_allowed",
        "not_in_catalog",
        "current",
    ]
    reason_text: str  # משפט בעברית, מוצג לעובד כמו שהוא


class TraceLine(BaseModel):
    """שורה ב"קבלה" של החישוב. כל מספר שהבוט אומר חייב להופיע כאן (Number Guard)."""

    key: str  # מזהה יציב, למשל "income_tax"
    label: str  # "מס הכנסה"
    amount: float
    formula: Optional[str] = None  # "מדרגות 2025 על 22,570 ₪ פחות 2.75 נק׳ זיכוי × 242"
    source: Optional[str] = None  # "strauss-rules.json · netMethod.brackets"


class WaterfallStep(BaseModel):
    """רכיב בהפרש הנטו בין היום לחלופה. סכום ה-steps = delta_net."""

    key: str
    label: str
    amount: float  # חיובי = מגדיל את הנטו


class OptionResult(BaseModel):
    option: OptionRequest
    label: str  # "BYD ATTO 3 (2025) · חשמלי" / "ויתור — אחזקת רכב"
    status: Literal["complete", "partial", "blocked"]
    missing: list[str] = []  # שמות שדות חסרים, למשל ["participation"]
    eligibility: Eligibility
    car: Optional[Car] = None  # רק לרכב מהקטלוג
    drive: Optional[Drive] = None  # סוג ההנעה לפי המאגר — גם לרכב מחוץ לקטלוג

    budget: float
    monthly_cost: Optional[float] = None
    employee_participation: Optional[float] = None
    family_gap_employee: float = 0
    value_of_use: float = 0
    electric_bonus_gross: float = 0
    maintenance: float = 0

    gross: Optional[float] = None
    taxable_income: Optional[float] = None
    income_tax: Optional[float] = None
    national_insurance: Optional[float] = None
    health_tax: Optional[float] = None
    pension_employee: Optional[float] = None
    study_fund_employee: Optional[float] = None
    net: Optional[float] = None
    delta_net: Optional[float] = None  # מול המצב היום, מדויק; None במצב הנוכחי עצמו. סכום ה-waterfall שווה לו
    # ההפרש כפי שמוצג: נטו מעוגל פחות נטו מעוגל — כך שהמספרים על המסך תמיד מסתדרים (כמו בגיליון הייחוס)
    delta_display: Optional[int] = None
    # נקודת האיזון: ההשתתפות החודשית המרבית ברכב הזה שבה הנטו עדיין לא יורד מתחת להיום.
    # מחושבת גם כשההשתתפות עצמה חסרה (ממתינים לנציג). שלילית = גם בלי השתתפות הנטו נמוך מהיום
    break_even_participation: Optional[float] = None

    explanation: str  # שתי שורות בעברית פשוטה, נבנה מה-trace
    trace: list[TraceLine] = []
    waterfall: list[WaterfallStep] = []


class CompareResponse(BaseModel):
    rules_version: str
    current: OptionResult
    alternatives: list[OptionResult]


# ---------- שאלות לנציג: /api/rep/* ----------


class RepAnswer(BaseModel):
    value: float | str
    effective_from: Optional[str] = None  # "2027-01-01"
    note: Optional[str] = None
    answered_by: Optional[str] = None


class RepQuestion(BaseModel):
    id: str
    conversation_id: str
    employee_display_name: str  # שם בלבד — בלי ת״ז ובלי נתוני שכר מלאים
    field: str  # השדה החסר, למשל "participation:CAR-10"
    question_text: str
    context: str  # תקציר קצר לנציג: קבוצה, רכב נוכחי, רכב מבוקש
    status: Literal["open", "answered"]
    created_at: datetime
    answer: Optional[RepAnswer] = None
    answered_at: Optional[datetime] = None


# ---------- שיחה: /api/chat ----------


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    text: str
    created_at: datetime
    # הודעת בוט יכולה לצרף השוואה — הממשק מציג אותה ככרטיס
    comparison: Optional[CompareResponse] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None  # None = שיחה חדשה
    message: str


class ConversationState(BaseModel):
    """מה שהממשק מקבל אחרי כל הודעה, ומה ש-GET /api/conversations/{id} מחזיר אחרי רענון."""

    conversation_id: str
    status: Literal["collecting", "waiting_for_rep", "ready"]
    employee_display_name: Optional[str] = None  # שם פרטי בלבד, לנציג
    messages: list[ChatMessage]
    profile: EmployeeProfile
    pending_questions: list[RepQuestion] = []
    last_comparison: Optional[CompareResponse] = None
