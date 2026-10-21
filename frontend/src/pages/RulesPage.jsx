// מסך הכללים — עריכה, ולידציה, ותצוגת השפעה על 6 העובדים לדוגמה לפני שמירה. בעלות: מפתחת ב'.
// "בפיילוט מחליפים נתונים, לא קוד": כל שינוי כאן נכנס לתוקף מיד בכל חישוב.
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import { Badge, Button, Card, Delta, Input, Money, Notice, SectionTitle } from "../design/components";

const clone = (o) => JSON.parse(JSON.stringify(o));

// השדות שמנהל/ת עורך/ת בפועל. כל השאר נשמר כמו שהוא
const FIELDS = [
  { path: ["electric", "netBonus"], label: "החזר חשמל (₪ נטו בחודש)", type: "number" },
  { path: ["familyTrack", "minChildren"], label: "מסלול משפחתי: מינימום ילדים", type: "number" },
  { path: ["familyTrack", "gapSplitEmployee"], label: "מסלול משפחתי: חלק העובד בפער (%)", type: "percent" },
  { path: ["netMethod", "creditPointValue"], label: "שווי נקודת זיכוי (₪)", type: "number" },
];

const get = (obj, path) => path.reduce((o, k) => o?.[k], obj);
function set(obj, path, value) {
  const next = clone(obj);
  path.slice(0, -1).reduce((o, k) => o[k], next)[path.at(-1)] = value;
  return next;
}

function ImpactTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-ink-soft">
            <th className="py-2 text-right font-medium">עובד/ת</th>
            <th className="py-2 text-right font-medium">השאלה</th>
            <th className="py-2 text-left font-medium">הפרש היום</th>
            <th className="py-2 text-left font-medium">הפרש אחרי השינוי</th>
            <th className="py-2 text-left font-medium">השינוי</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const change = r.delta != null && r.before.delta != null ? r.delta - r.before.delta : null;
            return (
              <tr key={r.employee_id} className={`border-t border-border/60 ${r.changed ? "bg-brand-soft/40" : ""}`}>
                <td className="py-2">
                  <div className="font-medium">{r.name}</div>
                  <div className="text-xs text-ink-soft">קבוצה {r.group}</div>
                </td>
                <td className="py-2 text-ink-soft">
                  <bdi>{r.alternative}</bdi>
                </td>
                <td className="num py-2 text-left">{r.before.delta != null ? <Delta value={r.before.delta} /> : "—"}</td>
                <td className="num py-2 text-left">{r.delta != null ? <Delta value={r.delta} /> : r.status === "blocked" ? "לא זכאי" : "—"}</td>
                <td className="py-2 text-left">
                  {r.changed ? change != null ? <Delta value={change} /> : <Badge tone="warn">השתנה</Badge> : <span className="text-xs text-ink-soft">ללא שינוי</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function RulesPage() {
  const [saved, setSaved] = useState(null); // הכללים כפי שהם בקובץ
  const [draft, setDraft] = useState(null);
  const [preview, setPreview] = useState(null);
  const [problems, setProblems] = useState([]);
  const [status, setStatus] = useState(null);
  const timer = useRef(null);

  const load = () =>
    api.rules().then((r) => {
      setSaved(r);
      setDraft(r);
    });

  useEffect(() => {
    load();
  }, []);

  // כל שינוי בטיוטה → תצוגת השפעה (בהשהיה קצרה, כדי לא לחשב על כל הקשה)
  useEffect(() => {
    if (!draft) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api
        .previewRules(draft)
        .then((p) => {
          setPreview(p);
          setProblems([]);
        })
        .catch((err) => {
          setPreview(null);
          setProblems(err.problems?.length ? err.problems : [err.message]);
        });
    }, 350);
    return () => clearTimeout(timer.current);
  }, [draft]);

  const dirty = useMemo(() => JSON.stringify(saved) !== JSON.stringify(draft), [saved, draft]);
  const changedCount = preview?.impact.filter((r) => r.changed).length ?? 0;

  async function save() {
    if (!window.confirm(`לשמור את הכללים? השינוי ייכנס לתוקף מיד בכל חישוב (${changedCount} מתוך 6 עובדי הדוגמה מושפעים).`)) return;
    try {
      const res = await api.saveRules(draft);
      setStatus(`נשמר ✓ גרסה ${res.version}. הגרסה הקודמת גובתה.`);
      await load();
    } catch (err) {
      setProblems(err.problems?.length ? err.problems : [err.message]);
    }
  }

  async function undo() {
    try {
      const res = await api.undoRules();
      setStatus(`שוחזרה הגרסה הקודמת: ${res.version}`);
      await load();
    } catch (err) {
      setStatus(err.message);
    }
  }

  if (!draft) return null;

  return (
    <div className="space-y-6">
      <section className="max-w-2xl">
        <h1 className="font-display text-3xl font-bold">כללי המערכת</h1>
        <p className="mt-2 text-ink-soft">
          עדכון כללי החישוב ותצוגת השפעתם על עובדי הדוגמה.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card className="glass space-y-5">
          <Input label="גרסה" value={draft.version} onChange={(e) => setDraft({ ...draft, version: e.target.value })} />

          <div>
            <div className="mb-2 text-sm font-medium">תקציב רכב חודשי לפי קבוצה (₪)</div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {draft.groupOrder.map((g) => (
                <Input
                  key={g}
                  label={`קבוצה ${g}`}
                  type="number"
                  value={draft.budgets[g]}
                  onChange={(e) => setDraft(set(draft, ["budgets", g], Number(e.target.value)))}
                />
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <Input
                key={f.path.join(".")}
                label={f.label}
                type="number"
                step="any"
                value={f.type === "percent" ? Math.round(get(draft, f.path) * 100) : get(draft, f.path)}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setDraft(set(draft, f.path, f.type === "percent" ? v / 100 : v));
                }}
              />
            ))}
            <label className="block text-sm">
              <span className="mb-1.5 block font-medium">שיטת החזר החשמל</span>
              <select
                value={draft.electric.method}
                onChange={(e) => setDraft(set(draft, ["electric", "method"], e.target.value))}
                className="w-full rounded-2xl border border-border bg-surface px-4 py-2.5 outline-none focus:border-brand"
              >
                <option value="gross_up">מגולם — העובד מקבל בדיוק את הסכום נטו</option>
                <option value="gross">ברוטו — הסכום חייב במס</option>
              </select>
            </label>
          </div>

          {problems.length > 0 && (
            <Notice>
              <div className="font-medium">הכללים לא תקינים — אי אפשר לשמור:</div>
              <ul className="mt-1 list-inside list-disc">
                {problems.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </Notice>
          )}
          {status && <Notice tone="brand">{status}</Notice>}

          <div className="flex flex-wrap gap-2">
            <Button onClick={save} disabled={!dirty || problems.length > 0}>
              שמירה
            </Button>
            <Button variant="secondary" onClick={() => setDraft(saved)} disabled={!dirty}>
              ביטול השינויים
            </Button>
            <Button variant="ghost" onClick={undo}>
              ↶ שחזור הגרסה הקודמת
            </Button>
          </div>
        </Card>

        <Card className="glass">
          <SectionTitle hint={dirty ? `${changedCount} מתוך 6 מושפעים` : "אין שינויים"}>השפעה על עובדי הדוגמה</SectionTitle>
          {preview ? (
            <ImpactTable rows={preview.impact} />
          ) : (
            <p className="text-sm text-ink-soft">{problems.length ? "תתקנו את הכללים כדי לראות השפעה." : "מחשב…"}</p>
          )}
          <p className="mt-4 text-xs text-ink-soft">
            הנטו היום של כל עובד: {preview?.impact.map((r) => (
              <span key={r.employee_id} className="me-2 inline-block">
                {r.name.split(" ")[0]} <Money value={r.net_today} />
              </span>
            ))}
          </p>
        </Card>
      </div>

      <details className="rounded-2xl border border-border/70 bg-surface/60 p-4">
        <summary className="cursor-pointer text-sm font-medium text-ink-soft">הקובץ המלא (JSON)</summary>
        <pre className="num mt-3 max-h-96 overflow-auto text-left text-xs">{JSON.stringify(draft, null, 2)}</pre>
      </details>
    </div>
  );
}
