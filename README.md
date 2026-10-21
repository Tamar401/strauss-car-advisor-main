# יועץ הרכב של שטראוס

איג'נט בעברית שעונה לעובד: "מה יקרה לנטו שלי אם אחליף רכב, אעבור לחשמלי או אוותר על הרכב?"

## עקרונות

1. **החישוב בקוד, לא במודל.** Gemini מחלץ נתונים, בוחר כלים ומנסח. כל מספר מגיע מהמנוע.
2. **לא מנחשים.** לכל נתון בפרופיל יש מקור (`employee` / `payslip` / `rep` / `catalog` / `rules` / `missing`). על נתון חסר המנוע לא רץ. במקום זה שואלים את העובד או שולחים שאלה לנציג.
3. **Number Guard.** כל מספר בתשובת הבוט חייב להופיע ב-trace של החישוב. אחרת התשובה נחסמת.
4. **כללים כנתונים.** `config/strauss-rules.json` עם ולידציה. בפיילוט מחליפים את הקובץ, לא את הקוד.

## הפעלה

```bash
# שרת (Python 3.12)
cd backend
pip install -r requirements.txt
cp .env.example .env          # רק אם .env עדיין לא קיים; ממלאים GEMINI_API_KEY
python -m uvicorn app.main:app --port 8000   # אחרי שינוי בקוד: לעצור ולהפעיל שוב (--reload נתקע אצלנו ב-Windows)
python -m pytest -q            # בדיקות

# ממשק (Node 20+), בטרמינל נוסף
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

חשבונות העובדים, הנציגים והשיחות הפרטיות נשמרים ב-`data/app.db`. מנהל/ת נכנס/ת דרך `/admin/login` עם `ADMIN_USERNAME` ו-`ADMIN_PASSWORD`. במסך הניהול ניתן להנפיק לנציג/ה קוד הרשמה חד-פעמי, הקשור לכתובת הדוא״ל ותקף ל-24 שעות; הנציג/ה בוחר/ת סיסמה בהרשמה דרך `/rep/register`, ובהמשך מתחבר/ת דרך `/rep/login`. עובדים נרשמים בנפרד דרך `/employee/register` עם שם מלא, כתובת דוא״ל וסיסמה; ניתן להוסיף גם מספר טלפון. מנהל/ת אינו/ה יוצר/ת חשבונות עובדים. כללי המערכת נמצאים במסך הנפרד `/rules`, ושמירתם דורשת התחברות מנהל/ת. שאלות פתוחות משותפות לצוות, ורק הנציג/ה שענה/תה רואה את השאלה בהיסטוריית המענה שלו/ה. קוד `REP_ACCESS_CODE` נשאר לחיפוש כלי רכב.

> **אזהרת פיתוח בלבד:** בלי `ADMIN_USERNAME` ו-`ADMIN_PASSWORD` לא ניתן להתחבר כמנהל/ת. אם `REP_ACCESS_CODE` חסר או ריק ב-`.env`, חיפוש כלי הרכב עשוי להיות נגיש ללא קוד. יש להגדיר את הפרטים לפני כל שימוש מחוץ לפיתוח מקומי; ראו `docs/PRIVACY.md`.

## מבנה

```
config/strauss-rules.json   כללי האתגר (תקציבים, מסלולים, שיטת הנטו)
data/raw/                   מאגר שווי השימוש (cp1255) + אקסל האתגר
data/seed/                  JSON שיוצא מהאקסל: catalog, occupations, employees, golden
backend/app/contracts.py    החוזים: מקור האמת למבני הנתונים
backend/app/engine/         המנוע: rules (כללים) · vou (מאגר שווי שימוש) · eligibility · net · compare
backend/app/agent/          הסוכן: orchestrator (לולאת Gemini) · tools · number_guard · prompts · rep_flow
backend/app/store.py        חשבונות, sessions, שיחות ושאלות לנציג ב-SQLite (data/app.db)
backend/app/api/            נתיבי ה-API (ראו docs/CONTRACTS.md)
backend/scripts/            export_seed.py: אקסל → seed
frontend/src/design/        מערכת העיצוב המשותפת (tokens + רכיבים), דוגמאות ב-/design
frontend/src/pages/         עובד · נציג · כללים · מערכת עיצוב
docs/                       חוזים, ממצאי נתונים, תוכנית עבודה
```

## בעלות

| | מפתחת א': המספרים והשקיפות | מפתחת ב': השיחה והאנשים |
|---|---|---|
| לוגיקה | `engine/` (נטו + trace), טעינת המאגר, תור הנציג | `rules`, זכאות, `agent/` (Gemini + כלים), Number Guard |
| API | `/api/compare`, `/api/rep/*` | `/api/chat`, `/api/conversations`, `/api/rules` |
| מסכים | השוואה + גרף מפל, מסך נציג | צ'אט + כרטיס פרופיל, מסך כללים |

כל Pull Request עובר review של השנייה.
