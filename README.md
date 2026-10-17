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
cp .env.example .env          # וממלאים GEMINI_API_KEY
python -m uvicorn app.main:app --port 8000   # אחרי שינוי בקוד: לעצור ולהפעיל שוב (--reload נתקע אצלנו ב-Windows)
python -m pytest -q            # בדיקות

# ממשק (Node 20+), בטרמינל נוסף
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

> **אזהרת פיתוח בלבד:** אם `REP_ACCESS_CODE` או `ADMIN_ACCESS_CODE` חסרים או ריקים ב-`.env`, מסך הנציג או מסך הכללים עשויים להיות נגישים ללא אימות. יש להגדיר את שניהם לפני כל שימוש מחוץ לפיתוח מקומי; ראו `docs/PRIVACY.md`.

## מבנה

```
config/strauss-rules.json   כללי האתגר (תקציבים, מסלולים, שיטת הנטו)
data/raw/                   מאגר שווי השימוש (cp1255) + אקסל האתגר
data/seed/                  JSON שיוצא מהאקסל: catalog, occupations, employees, golden
backend/app/contracts.py    החוזים: מקור האמת למבני הנתונים
backend/app/engine/         המנוע: rules (כללים) · vou (מאגר שווי שימוש) · eligibility · net · compare
backend/app/agent/          הסוכן: orchestrator (לולאת Gemini) · tools · number_guard · prompts · rep_flow
backend/app/store.py        שמירת שיחות ושאלות לנציג ב-SQLite (data/app.db)
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
