// מסך העובד — הצ'אט וכרטיס הפרופיל: מפתחת ב'. אזור ההשוואה: מפתחת א'.
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import { useAuth } from "../auth";
import ComparisonGrid from "../components/ComparisonGrid";
import ProfileCard from "../components/ProfileCard";
import { Button, Card, ChatBubble, Notice, PetalMark, SectionTitle } from "../design/components";

const STORAGE_KEY = "conversation_id";
const POLL_MS = 3000;

const STARTERS = [
  "אני שוקל/ת לעבור לרכב חשמלי. כמה זה ישנה לי בנטו?",
  "מה יקרה לנטו אם אוותר על הרכב?",
  "יש לי 4 ילדים, מגיע לי רכב משפחתי?",
];

function storageKey(userId) {
  return `${STORAGE_KEY}:${userId}`;
}

function readStoredId(userId) {
  try {
    return localStorage.getItem(storageKey(userId));
  } catch {
    return null;
  }
}

function storeId(userId, id) {
  try {
    if (id) localStorage.setItem(storageKey(userId), id);
    else localStorage.removeItem(storageKey(userId));
  } catch {
    /* מצב פרטי — השיחה פשוט לא תשוחזר אחרי רענון */
  }
}

function TypingBubble() {
  return (
    <ChatBubble role="assistant">
      <span className="inline-flex gap-1" aria-label="היועץ מקליד">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-2 w-2 animate-bounce rounded-full bg-ink-soft/60" style={{ animationDelay: `${i * 150}ms` }} />
        ))}
      </span>
    </ChatBubble>
  );
}

export default function EmployeePage() {
  const { user } = useAuth();
  const [state, setState] = useState(null);
  const [text, setText] = useState("");
  const [pending, setPending] = useState(null); // ההודעה שנשלחה ועוד לא נענתה
  const [error, setError] = useState(null);
  const [catalog, setCatalog] = useState({});
  const [demos, setDemos] = useState([]);
  const [exploring, setExploring] = useState(false);
  const [exploreError, setExploreError] = useState(null);
  const endRef = useRef(null);
  const busy = pending != null;

  useEffect(() => {
    const id = readStoredId(user.id);
    if (id) api.conversation(id).then(setState).catch(() => storeId(user.id, null));
    api.catalog().then((cars) => setCatalog(Object.fromEntries(cars.map((c) => [c.id, c]))));
    api.demoEmployees().then(setDemos);
  }, [user.id]);

  // ממתינים לנציג: מושכים את השיחה כל כמה שניות, וכשהוא עונה — ההשוואה מתעדכנת לבד
  useEffect(() => {
    if (state?.status !== "waiting_for_rep" || busy) return;
    const t = setInterval(() => {
      api.conversation(state.conversation_id).then(setState).catch(() => {});
    }, POLL_MS);
    return () => clearInterval(t);
  }, [state?.status, state?.conversation_id, busy]);

  // בסוגריים מסולסלים בכוונה: בדפדפנים חדשים scrollIntoView מחזיר Promise, ו-React ינסה להפעיל אותו כ-cleanup
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [state?.messages.length, pending]);

  async function send(message) {
    const clean = message.trim();
    if (!clean || busy) return;
    setPending(clean);
    setText("");
    setError(null);
    try {
      const next = await api.chat(state?.conversation_id ?? null, clean);
      storeId(user.id, next.conversation_id);
      setState(next);
    } catch (err) {
      setError(err.message);
      setText(clean);
    } finally {
      setPending(null);
    }
  }

  async function loadDemo(employeeId) {
    setError(null);
    try {
      const next = await api.loadDemo(state?.conversation_id, employeeId);
      storeId(user.id, next.conversation_id);
      setState(next);
    } catch (err) {
      setError(err.message);
    }
  }

  async function explore() {
    setExploring(true);
    setExploreError(null);
    try {
      setState(await api.explore(state.conversation_id));
    } catch (err) {
      setExploreError(err.message);
    } finally {
      setExploring(false);
    }
  }

  function reset() {
    storeId(user.id, null);
    setState(null);
    setExploreError(null);
  }

  // ההשוואה האחרונה שצורפה להודעה — כך הכרטיסים תמיד תואמים למה שהבוט אמר
  const comparison = [...(state?.messages ?? [])].reverse().find((m) => m.comparison)?.comparison;
  const messages = state?.messages ?? [];

  return (
    <div className="space-y-8">
      <section className="max-w-2xl">
        <h1 className="font-display text-3xl font-bold leading-tight sm:text-5xl">
          מה יקרה <span className="petal-text">לנטו שלי?</span>
        </h1>
        <p className="mt-3 text-ink-soft sm:text-lg">
          רכב חשמלי, רכב אחר או ויתור על הרכב: תשובה מדויקת תוך דקה, עם הסבר לכל שקל.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
        <Card className="glass flex h-[72vh] min-h-[480px] flex-col p-0">
          <div className="flex items-center justify-between border-b border-border/70 px-5 py-3">
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <PetalMark size={30} />
                <span className="absolute -bottom-0.5 -left-0.5 h-2.5 w-2.5 rounded-full border-2 border-surface bg-up" />
              </div>
              <div className="leading-tight">
                <div className="font-display font-bold">יועץ הרכב</div>
                <div className="text-xs text-ink-soft">
                  {busy ? "מקליד…" : state?.status === "waiting_for_rep" ? "ממתין לתשובת הנציג" : "זמין עכשיו"}
                </div>
              </div>
            </div>
            <Button variant="ghost" onClick={reset}>
              שיחה חדשה
            </Button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-5 py-5">
            {messages.length === 0 && !busy && (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                <PetalMark size={56} />
                <p className="max-w-xs text-sm text-ink-soft">במה אפשר לעזור? אפשר לכתוב חופשי, או להתחיל מכאן:</p>
                <div className="flex flex-col gap-2">
                  {STARTERS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-border bg-surface px-4 py-2 text-sm transition hover:border-brand hover:text-brand"
                    >
                      {s}
                    </button>
                  ))}
                </div>
                {demos.length > 0 && (
                  <div className="mt-2 text-xs text-ink-soft">
                    <div className="mb-2">או לטעון נתוני דמו:</div>
                    <div className="flex flex-wrap justify-center gap-1.5">
                      {demos.map((d) => (
                        <button
                          key={d.id}
                          onClick={() => loadDemo(d.id)}
                          className="rounded-full bg-muted px-3 py-1 transition hover:bg-brand-soft hover:text-brand"
                        >
                          {d.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            {messages.map((m) =>
              m.role === "system" ? (
                <div key={m.id} className="animate-rise text-center">
                  <span className="inline-block rounded-full bg-muted px-3 py-1 text-xs text-ink-soft">{m.text}</span>
                </div>
              ) : (
                <ChatBubble key={m.id} role={m.role}>
                  {m.text}
                </ChatBubble>
              ),
            )}
            {pending && <ChatBubble role="user">{pending}</ChatBubble>}
            {pending && <TypingBubble />}
            <div ref={endRef} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
            className="flex gap-2 border-t border-border/70 p-3"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="כתבו כאן…"
              className="flex-1 rounded-full border border-border bg-surface px-4 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
            />
            <Button type="submit" disabled={busy}>
              שליחה
            </Button>
          </form>
          {error && <div className="px-5 pb-3 text-sm text-down">{error}</div>}
          <p className="px-5 pb-3 text-[11px] leading-snug text-ink-soft">
            🔒 אין צורך בתעודת זהות. נתוני השכר משמשים רק לחישוב, והשיחה נמחקת אוטומטית אחרי 30 יום. החישוב עצמו מתבצע בשרת לפי כללי החברה.
          </p>
        </Card>

        <div className="space-y-6">
          {state && <ProfileCard state={state} catalog={catalog} onUpdated={setState} />}

          {state?.pending_questions?.length > 0 && (
            <Notice>
              ⏳ שאלתי את נציג התחבורה: {state.pending_questions.map((q) => q.question_text).join(" · ")}
              <br />
              ההשוואה תתעדכן כאן לבד ברגע שיענה.
            </Notice>
          )}

          <div>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <SectionTitle hint={comparison ? `כללים: ${comparison.rules_version}` : undefined}>ההשוואה שלך</SectionTitle>
              {state && (
                <Button variant="secondary" onClick={explore} disabled={exploring || busy}>
                  {exploring ? "מחשב…" : "✨ כל האפשרויות שלי"}
                </Button>
              )}
            </div>
            {exploreError && <Notice>{exploreError}</Notice>}
            {comparison ? (
              <ComparisonGrid comparison={comparison} />
            ) : (
              <Card className="glass flex flex-col items-center gap-3 py-12 text-center">
                <div className="petal-ribbon h-1.5 w-24 rounded-full opacity-70" />
                <p className="max-w-sm text-sm text-ink-soft">
                  ההשוואה תופיע כאן ברגע שיהיו מספיק נתונים: כל חלופה עם הנטו המשוער, ההפרש מול היום, והסבר במילים פשוטות.
                </p>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
