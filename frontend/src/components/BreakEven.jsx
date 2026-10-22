// נקודת האיזון: עד איזו השתתפות חודשית הרכב עדיין משתלם. מחושבת בשרת, גם כשההשתתפות עוד לא ידועה.
import { fmt } from "../design/format";

export default function BreakEven({ result }) {
  const b = result.break_even_participation;
  if (b == null) return null;
  const limit = Math.floor(b); // מעוגל כלפי מטה — לצד הבטוח

  if (limit <= 0) {
    return (
      <div className="mt-4 rounded-2xl bg-down-soft px-4 py-3 text-sm">
        <span className="font-medium">⚖️ נקודת האיזון:</span> גם בלי השתתפות בכלל, הנטו ברכב הזה נמוך מהיום.
      </div>
    );
  }

  const p = result.employee_participation;
  const over = p != null && p > limit;
  return (
    <div className={`mt-4 rounded-2xl px-4 py-3 ${over ? "bg-down-soft" : "bg-up-soft"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="text-sm font-medium">⚖️ נקודת האיזון</span>
        <span className="num font-display font-bold">השתתפות עד {fmt(limit)}</span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-ink-soft">
        {p == null
          ? "עוד לפני תשובת הנציג: כל השתתפות עד הסכום הזה משאירה את הנטו שלך גבוה מהיום."
          : over
            ? `ההשתתפות שלך (${fmt(p)}) גבוהה מנקודת האיזון ב-${fmt(p - limit)}.`
            : `ההשתתפות שלך (${fmt(p)}) — עוד ${fmt(limit - p)} מרווח עד שזה מפסיק להשתלם.`}
      </p>
      {p != null && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface/70" aria-hidden="true">
          <div className={`h-full rounded-full ${over ? "bg-down" : "bg-up"}`} style={{ width: `${Math.min(100, (p / limit) * 100)}%` }} />
        </div>
      )}
    </div>
  );
}
