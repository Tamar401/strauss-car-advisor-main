// מסך הנציג — בעלות: מפתחת א'. שני סוגי שאלות: השתתפות ברכב חדש (סכום), וזיהוי הרכב של היום (בחירה מהמאגר).
import { useEffect, useState } from "react";

import { api } from "../api";
import { Badge, Button, Card, Input, Money, SectionTitle } from "../design/components";

function ParticipationForm({ q, onAnswered }) {
  const [value, setValue] = useState("");
  const [from, setFrom] = useState("");
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    try {
      await api.answerQuestion(q.id, { value: Number(value), effective_from: from || null });
      onAnswered();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <Input label="השתתפות חודשית (₪)" type="number" min="0" required value={value} onChange={(e) => setValue(e.target.value)} />
      <Input label="בתוקף מ-" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
      <Button type="submit">שליחה לעובד</Button>
      {error && <div className="text-sm text-down sm:col-span-3">{error}</div>}
    </form>
  );
}

function VehiclePicker({ q, onAnswered }) {
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [results, setResults] = useState(null);
  const [chosen, setChosen] = useState(null);
  const [error, setError] = useState(null);

  async function search(e) {
    e.preventDefault();
    setError(null);
    setChosen(null);
    try {
      setResults(await api.searchVehicles(query, year || null));
    } catch (err) {
      setError(err.message);
    }
  }

  async function submit() {
    try {
      await api.answerQuestion(q.id, { value: chosen });
      onAnswered();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="mt-4 space-y-3">
      <form onSubmit={search} className="grid gap-3 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
        <Input label="יצרן / דגם / קוד דגם" placeholder="COROLLA" required value={query} onChange={(e) => setQuery(e.target.value)} />
        <Input label="שנת רישום" type="number" placeholder="2021" value={year} onChange={(e) => setYear(e.target.value)} />
        <Button type="submit" variant="secondary">
          חיפוש במאגר
        </Button>
      </form>
      {results && (
        <div className="max-h-72 overflow-y-auto rounded-2xl border border-border/70">
          {results.candidates.length === 0 && <div className="p-3 text-sm text-ink-soft">לא נמצא — לנסות בלי שנה, או לפי קוד הדגם מהרישיון</div>}
          {results.candidates.map((c) => (
            <label
              key={c.vou_key}
              className={`flex cursor-pointer items-center gap-3 border-b border-border/50 px-3 py-2 text-sm last:border-0 ${chosen === c.vou_key ? "bg-brand-soft/50" : "hover:bg-muted"}`}
            >
              <input type="radio" name={`v-${q.id}`} checked={chosen === c.vou_key} onChange={() => setChosen(c.vou_key)} />
              <span className="flex-1">
                <bdi className="font-medium">{c.name}</bdi>
                <span className="text-ink-soft">
                  {" "}· <bdi>{c.trim}</bdi> · קוד {c.model_code}
                  {c.engine_cc ? ` · ${c.engine_cc.toLocaleString("he-IL")} סמ״ק` : ""} · {c.drive}
                </span>
              </span>
              <span className="text-left text-xs text-ink-soft">
                מחירון <Money value={c.list_price} />
                <br />
                שווי שימוש <Money value={c.value_of_use} />
              </span>
            </label>
          ))}
          {results.total > results.candidates.length && (
            <div className="p-2 text-center text-xs text-ink-soft">
              מוצגות {results.candidates.length} מתוך {results.total} — כדאי לצמצם בשנה או בקוד דגם
            </div>
          )}
        </div>
      )}
      {error && <div className="text-sm text-down">{error}</div>}
      <Button onClick={submit} disabled={!chosen}>
        זה הרכב — שליחה לעובד
      </Button>
    </div>
  );
}

function QuestionCard({ q, onAnswered }) {
  const isVehicle = q.field === "current_vehicle";
  return (
    <Card className="glass">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-display font-bold">{q.employee_display_name}</div>
          <div className="text-xs text-ink-soft">{q.context}</div>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Badge tone="brand">{isVehicle ? "🚗 זיהוי רכב" : "₪ השתתפות"}</Badge>
          <Badge tone={q.status === "open" ? "warn" : "up"}>{q.status === "open" ? "פתוחה" : "נענתה"}</Badge>
        </div>
      </div>
      <p className="mt-3 text-sm">{q.question_text}</p>
      {q.status === "open" ? (
        isVehicle ? (
          <VehiclePicker q={q} onAnswered={onAnswered} />
        ) : (
          <ParticipationForm q={q} onAnswered={onAnswered} />
        )
      ) : (
        <div className="mt-3 text-sm text-up">
          נענתה: <span className="num">{String(q.answer.value)}</span>
          {q.answer.effective_from && ` · בתוקף מ-${q.answer.effective_from}`}
        </div>
      )}
    </Card>
  );
}

export default function RepPage() {
  const [questions, setQuestions] = useState([]);
  const load = () => api.repQuestions().then(setQuestions).catch(() => {});

  useEffect(() => {
    load();
    // שאלות חדשות מופיעות בלי רענון; כשהלשונית מוסתרת לא פונים לשרת, ובחזרה אליה מתעדכנים מיד
    const t = setInterval(() => !document.hidden && load(), 3000);
    const onVisible = () => !document.hidden && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const open = questions.filter((q) => q.status === "open");
  const answered = questions.filter((q) => q.status !== "open");

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <SectionTitle hint={`${open.length} פתוחות`}>שאלות מעובדים</SectionTitle>
      <p className="text-sm text-ink-soft">
        שאלות פתוחות זמינות לצוות הנציגים. שאלות שנענו מוצגות כאן רק אם נענו על ידך.
      </p>
      {questions.length === 0 && (
        <Card className="glass py-10 text-center text-sm text-ink-soft">
          אין שאלות כרגע. כשהבוט יצטרך מידע שהעובד לא יודע, השאלה תופיע כאן — והתשובה שלך תעדכן את השיחה של העובד מיד.
        </Card>
      )}
      {open.map((q) => (
        <QuestionCard key={q.id} q={q} onAnswered={load} />
      ))}
      {answered.length > 0 && (
        <details className="rounded-2xl border border-border/70 bg-surface/60 p-4">
          <summary className="cursor-pointer text-sm font-medium text-ink-soft">{answered.length} שאלות שנענו</summary>
          <div className="mt-3 space-y-3">
            {answered.map((q) => (
              <QuestionCard key={q.id} q={q} onAnswered={load} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
