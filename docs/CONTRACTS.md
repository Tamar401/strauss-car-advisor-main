# חוזים בין השכבות

מקור האמת הוא `backend/app/contracts.py`. המסמך הזה מסביר אותו. משנים חוזה רק בהסכמה של שתיכן, ומריצים `pytest` אחרי כל שינוי.

## נתיבים

| נתיב | מצב | בעלות | מחזיר |
|---|---|---|---|
| `GET /api/catalog` | אמיתי | משותף | `list[Car]` |
| `GET /api/occupations` | אמיתי | משותף | `list[Occupation]` |
| `GET /api/demo-employees` | אמיתי | משותף | 6 העובדים לדוגמה, בלי ת״ז |
| `GET /api/rules` | אמיתי | ב' | קובץ הכללים |
| `POST /api/rules/preview` | אמיתי | ב' | `{valid, version, impact}` ← ולידציה + ההשפעה על 6 העובדים לדוגמה (לפני/אחרי). לא שומר. על כללים לא תקינים מוחזר 422 עם `detail: {message, problems}` |
| `PUT /api/rules` | אמיתי | ב' | שומר אחרי ולידציה; הגרסה הקודמת נשמרת ב-`config/history/`. ⚠️ בפיילוט: רק למנהלים מחוברים |
| `POST /api/rules/undo` | אמיתי | ב' | משחזר את הגרסה האחרונה מההיסטוריה (404 אם אין) |
| `POST /api/conversations/{id}/explore` | אמיתי | א' | כל החלופות בבת אחת, בלי מודל שפה. 409 אם הפרופיל לא שלם |
| `GET /api/vehicles/search?q=&year=` | אמיתי, **קוד נציג** | א' | חיפוש במאגר המלא — לזיהוי הרכב של היום |
| `GET /api/auth/check/{rep\|admin}` | אמיתי | משותף | 200 אם הקוד בכותרת `X-Access-Code` פותח את המסך |

**הרשאות:** `/api/rep/*` ו-`/api/vehicles/search` דורשים קוד נציג (או מנהל). `POST /api/rules/preview`, `PUT /api/rules`, `POST /api/rules/undo` דורשים קוד מנהל. קוד שלא הוגדר ב-`.env` = מצב פיתוח פתוח.

**רכב מחוץ לקטלוג:** `OptionRequest` עם `vou_key` (ובלי `car_id`) — רק כמצב היום. כחלופה הוא `blocked` עם `not_in_catalog`. רכב בלי שניהם = "טרם זוהה": המצב היום `partial` עם `missing=["current_vehicle"]`, ושאלה לנציג מסוג `current_vehicle` (התשובה: מפתח מהמאגר, לא טקסט חופשי).
| `POST /api/compare` | אמיתי | א' | `CompareResponse` (400 על רכב לא מוכר) |
| `POST /api/compare/all` | אמיתי | א' | כל רכב בקטלוג + ויתור, ממוין: מחושבות לפי ההפרש, אחריהן חלקיות, בסוף לא זמינות |
| `GET /api/demo/compare/{id}` | אמיתי | משותף | `compare/all` לאחד מ-6 העובדים לדוגמה |
| `POST /api/chat` | אמיתי (Gemini + כלים) | ב' | `ConversationState` |
| `GET /api/conversations/{id}` | אמיתי (SQLite) | ב' | `ConversationState`, כולל `pending_questions` |
| `POST /api/conversations/{id\|new}/demo/{employee_id}` | אמיתי | ב' | ממלא את הפרופיל מעובד לדוגמה, בלי מודל |
| `GET /api/rep/questions?status=open` | אמיתי (SQLite) | א' | `list[RepQuestion]` |
| `POST /api/rep/questions/{id}/answer` | אמיתי | א' | `RepQuestion`. 409 אם כבר נענתה, 400 על השתתפות שלילית |

## מושגים מרכזיים

**`Tracked[T]`**: ערך ומקור. `source="missing"` אומר שהערך לא ידוע. המנוע מחזיר `status="partial"` ומוסיף את השדה ל-`missing`. הוא אף פעם לא ממלא ערך בעצמו.

**`OptionResult.status`**
- `complete`: יש את כל הנתונים, כל המספרים מחושבים.
- `partial`: חסר נתון (בדרך כלל השתתפות). נשלחה שאלה לנציג. `net` ו-`delta_net` הם `null`.
- `blocked`: אין זכאות. `eligibility.reason_text` מסביר למה.

**`trace`**: הקבלה של החישוב. ה-Number Guard בודק את הטקסט של הבוט מול השדות `amount` שבה.

**`waterfall`**: פירוק ההפרש. סכום ה-`amount` שווה בדיוק ל-`delta_net`. יש לזה בדיקה.

**`delta_net` מול `delta_display`**: `delta_net` הוא ההפרש המדויק. `delta_display` הוא נטו מעוגל פחות נטו מעוגל, וזה מה **שמציגים** (בכרטיס ובטקסט של הבוט). אחרת העובד יכול לראות 15,047 ← 13,109 ולצידם "−1,939". גם גיליון הייחוס מחשב כך.

**השתתפות ברכב חדש**:
- `participation` לא נשלח (None) ← ברירת המחדל מהקטלוג, ומסומנת ב-trace כ"קטלוג (ברירת מחדל)".
- `participation` נשלח עם `source="missing"` ← החלופה `partial`, ושואלים את הנציג.
הסוכן מחליט איזה מהשניים לפי מה שהעובד אמר.

**קבוצת הזכאות**: כשהעיסוק ידוע, הקבוצה נקבעת לפי טבלת העיסוקים ולא לפי מה שהעובד הקליד.

**עיגול**: השרת מחזיר ערכים בלי עיגול. הממשק מעגל לשקל ב-`design/format.js`.

## הזרימה כשחסר נתון

1. הסוכן מזהה שחסרה השתתפות לרכב X. הוא יוצר `RepQuestion` עם `field="participation:CAR-XX"`, וה-`status` של השיחה הופך ל-`waiting_for_rep`.
2. העובד רואה השוואה חלקית (`partial`) עם ההודעה "שאלתי את הנציג".
3. הנציג עונה. הערך נכנס לפרופיל עם `source="rep"` ו-`note` (תאריך תחולה), ומתבצע חישוב מחדש.
4. הממשק של העובד מושך את `GET /api/conversations/{id}` כל 3 שניות ורואה את ההשוואה המעודכנת.
