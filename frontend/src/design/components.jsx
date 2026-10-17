/**
 * מערכת העיצוב המשותפת. כל מסך בונים מהרכיבים האלה — ככה האפליקציה נראית אחידה
 * גם כששתי מפתחות בונות מסכים שונים. רכיב חדש שימושי לשתיכן? מוסיפים כאן + לעמוד /design.
 */
import { fmt, fmtDelta } from "./format";

const cx = (...c) => c.filter(Boolean).join(" ");

/** אייקון הבוט: הפרח מלוגו שטראוס, בלי הכיתוב (public/strauss-flower.svg). size בפיקסלים */
export function PetalMark({ size = 32, className }) {
  return (
    <img
      src="/strauss-flower.svg"
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      className={cx("object-contain", className)}
      style={{ width: size, height: size }}
    />
  );
}

export function Button({ variant = "primary", className, ...props }) {
  const styles = {
    primary:
      "text-white shadow-glow bg-gradient-to-l from-petal-red to-petal-orange hover:brightness-105 active:scale-[.98]",
    secondary: "bg-brand-soft text-brand hover:bg-brand-soft/70",
    ghost: "text-ink-soft hover:bg-muted",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition disabled:opacity-50",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, interactive = false, children, ...props }) {
  return (
    <div
      className={cx(
        "rounded-3xl border border-border/70 bg-surface p-5 shadow-card",
        interactive && "transition duration-200 hover:-translate-y-0.5 hover:shadow-lift",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children, hint }) {
  return (
    <div className="mb-4 flex items-baseline gap-3">
      <h2 className="font-display text-xl font-bold">{children}</h2>
      {hint && <span className="text-sm text-ink-soft">{hint}</span>}
    </div>
  );
}

export function Input({ label, hint, className, ...props }) {
  return (
    <label className={cx("block text-sm", className)}>
      {label && <span className="mb-1.5 block font-medium">{label}</span>}
      <input
        className="w-full rounded-2xl border border-border bg-surface px-4 py-2.5 outline-none transition focus:border-brand focus:ring-4 focus:ring-brand/15"
        {...props}
      />
      {hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>}
    </label>
  );
}

export function Badge({ tone = "neutral", children }) {
  const tones = {
    neutral: "bg-muted text-ink-soft",
    brand: "bg-brand-soft text-brand",
    up: "bg-up-soft text-up",
    down: "bg-down-soft text-down",
    warn: "bg-warn-soft text-warn",
  };
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

/** מאיפה הגיע הנתון — מקביל ל-Source ב-contracts.py */
const SOURCES = {
  employee: { label: "הקלדת", tone: "brand" },
  payslip: { label: "מהתלוש", tone: "brand" },
  rep: { label: "מהנציג", tone: "up" },
  catalog: { label: "ברירת מחדל", tone: "neutral" },
  rules: { label: "לפי הכללים", tone: "neutral" },
  missing: { label: "חסר", tone: "warn" },
};

export function SourceBadge({ source }) {
  const s = SOURCES[source] ?? SOURCES.missing;
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

/** סטטוס חלופה — מקביל ל-OptionResult.status */
const STATUS = {
  complete: { label: "מחושב", tone: "up", icon: "✓" },
  partial: { label: "ממתין לנציג", tone: "warn", icon: "⏳" },
  blocked: { label: "לא זכאי", tone: "down", icon: "✕" },
};

export function StatusBadge({ status }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone}>
      <span aria-hidden="true">{s.icon}</span>
      {s.label}
    </Badge>
  );
}

/** סוג הנעה → צבע עלה. ויתור = צהוב */
export const DRIVE = {
  electric: { label: "חשמלי", petal: "teal", icon: "⚡" },
  plugin: { label: "פלאג-אין", petal: "blue", icon: "🔌" },
  hybrid: { label: "היברידי", petal: "green", icon: "🍃" },
  petrol: { label: "בנזין", petal: "orange", icon: "⛽" },
  waiver: { label: "ויתור", petal: "yellow", icon: "💰" },
};

export function DriveTag({ drive }) {
  const d = DRIVE[drive];
  if (!d) return null;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        `bg-petal-${d.petal}/15 text-petal-${d.petal}`,
      )}
    >
      <span aria-hidden="true">{d.icon}</span>
      {d.label}
    </span>
  );
}

export function Money({ value, className }) {
  // whitespace-nowrap: "₪" לא נשבר לשורה נפרדת בטלפון
  return <span className={cx("num whitespace-nowrap", className)}>{fmt(value)}</span>;
}

/** הפרש נטו: צבע + חץ (לא מסתמכים על צבע בלבד) */
export function Delta({ value, size = "md" }) {
  if (value == null) return <span className="text-ink-soft">—</span>;
  const r = Math.round(value);
  const tone = r > 0 ? "bg-up-soft text-up" : r < 0 ? "bg-down-soft text-down" : "bg-muted text-ink-soft";
  const arrow = r > 0 ? "▲" : r < 0 ? "▼" : "•";
  const sizes = {
    md: "px-2.5 py-0.5 text-sm",
    lg: "px-3.5 py-1 text-xl font-display font-bold",
  };
  return (
    <span className={cx("inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full", tone, sizes[size])}>
      <span aria-hidden="true" className="text-[0.7em]">
        {arrow}
      </span>
      <span className="num">{fmtDelta(value)}</span>
    </span>
  );
}

export function Stat({ label, children, sub }) {
  return (
    <div>
      <div className="text-xs text-ink-soft">{label}</div>
      <div className="mt-0.5 font-display text-2xl font-bold">{children}</div>
      {sub && <div className="text-xs text-ink-soft">{sub}</div>}
    </div>
  );
}

export function ChatBubble({ role, children }) {
  const mine = role === "user";
  return (
    <div className={cx("flex items-end gap-2 animate-rise", mine ? "justify-start" : "justify-end")}>
      {!mine && <div className="order-last shrink-0 rounded-full bg-surface p-1 shadow-card"><PetalMark size={22} /></div>}
      <div
        className={cx(
          "max-w-[82%] whitespace-pre-line rounded-3xl px-4 py-2.5 text-sm leading-relaxed",
          mine
            ? "rounded-br-md bg-gradient-to-l from-petal-red to-petal-orange text-white shadow-glow"
            : "rounded-bl-md border border-border/70 bg-surface shadow-card",
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function Notice({ tone = "warn", children }) {
  const tones = {
    warn: "bg-warn-soft text-warn border-petal-yellow/40",
    brand: "bg-brand-soft text-brand border-brand/20",
  };
  return <div className={cx("rounded-2xl border px-4 py-3 text-sm", tones[tone])}>{children}</div>;
}
