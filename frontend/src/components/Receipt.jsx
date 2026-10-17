// "איך חישבנו?" — כל שורה בחישוב, היום מול החלופה, עם הנוסחה והמקור. בעלות: מפתחת א'.
// זו גם תצוגת הטבלה של גרף המפל (נגישות): כל מספר בגרף מופיע כאן במלואו.
import { fmt } from "../design/format";

// שורות שמראים גם כשהן 0 בצד אחד (למשל שווי שימוש שבוטל בוויתור)
const ALWAYS = new Set(["value_of_use", "participation", "maintenance", "electric_bonus_gross", "family_gap_employee"]);

export default function Receipt({ current, alt, defaultOpen = false }) {
  const today = Object.fromEntries((current?.trace ?? []).map((t) => [t.key, t]));
  const keys = [];
  for (const t of [...(current?.trace ?? []), ...alt.trace]) {
    if (!keys.includes(t.key)) keys.push(t.key);
  }
  // הסדר של החלופה קובע, והשורה "נטו" תמיד אחרונה
  const altByKey = Object.fromEntries(alt.trace.map((t) => [t.key, t]));
  const ordered = [...alt.trace.map((t) => t.key), ...keys.filter((k) => !altByKey[k])].filter((k) => k !== "net");
  ordered.push("net");

  return (
    <details open={defaultOpen} className="group mt-3 rounded-2xl border border-border/70 bg-muted/40 text-xs open:bg-surface">
      <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 font-medium text-ink-soft hover:text-ink">
        <span>🧾 איך חישבנו?</span>
        <span className="transition group-open:rotate-180" aria-hidden="true">
          ⌄
        </span>
      </summary>
      <div className="overflow-x-auto px-3 pb-3">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-ink-soft">
              <th className="py-1.5 text-right font-medium">רכיב</th>
              <th className="py-1.5 text-left font-medium">היום</th>
              <th className="py-1.5 text-left font-medium">בחלופה</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((key) => {
              const a = altByKey[key];
              const c = today[key];
              const line = a ?? c;
              if (!ALWAYS.has(key) && !a && !c?.amount) return null;
              const isNet = key === "net";
              return (
                <tr key={key} className={`border-t border-border/50 align-top ${isNet ? "font-bold" : ""}`}>
                  <td className="py-1.5 pe-2">
                    <div>{line.label}</div>
                    {a?.formula && <div className="mt-0.5 text-[11px] leading-snug text-ink-soft">{a.formula}</div>}
                    {a?.source && <div className="mt-0.5 text-[11px] text-ink-soft/80">מקור: {a.source}</div>}
                  </td>
                  <td className="num whitespace-nowrap py-1.5 ps-2 text-left text-ink-soft">{c ? fmt(c.amount) : "—"}</td>
                  <td className="num whitespace-nowrap py-1.5 ps-2 text-left">{a ? fmt(a.amount) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-2 text-[11px] text-ink-soft">
          החישוב מתבצע בקוד לפי קובץ הכללים, ללא עיגול; העיגול לשקל רק בתצוגה.
        </p>
      </div>
    </details>
  );
}
