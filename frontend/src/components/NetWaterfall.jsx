// פירוק ההפרש בנטו לרכיבים — עמודות מתפצלות מקו האפס. בעלות: מפתחת א'.
// ירוק = מגדיל את הנטו, אדום = מקטין. הצבע אף פעם לא לבד: יש גם חץ, סימן ומספר.
// הטקסט תמיד בצבעי טקסט (לא בצבע העמודה), כמו שמחייבת מערכת העיצוב.
import { useState } from "react";

import { fmtDelta } from "../design/format";

export default function NetWaterfall({ steps, total }) {
  const [hover, setHover] = useState(null);
  if (!steps?.length) return null;

  const max = Math.max(...steps.map((s) => Math.abs(s.amount)), 1);
  const hasUp = steps.some((s) => s.amount > 0);
  const hasDown = steps.some((s) => s.amount < 0);
  // כל הרכיבים לאותו כיוון → קו האפס בקצה והעמודות מנצלות את כל הרוחב; אחרת — באמצע
  const zero = hasUp && hasDown ? 50 : hasUp ? 0 : 100;
  const span = hasUp && hasDown ? 50 : 100;

  return (
    <figure className="mt-4" aria-label="פירוק ההפרש בנטו לפי רכיבים">
      <figcaption className="mb-2 text-xs font-medium text-ink-soft">ממה מורכב ההפרש</figcaption>
      <div className="space-y-1.5">
        {steps.map((s) => {
          const up = s.amount > 0;
          const width = `${(Math.abs(s.amount) / max) * span}%`;
          return (
            <div
              key={s.key}
              className="group relative grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)_4.5rem] items-center gap-2 text-xs"
              onMouseEnter={() => setHover(s.key)}
              onMouseLeave={() => setHover(null)}
            >
              <span className="truncate text-ink-soft" title={s.label}>
                {s.label}
              </span>
              {/* המסלול: קו אפס באמצע; חיובי נמתח ימינה, שלילי שמאלה — כמו ציר מספרים, בלי תלות בכיוון השפה */}
              <div className="relative h-4" dir="ltr">
                <div className="absolute inset-y-0 w-px bg-border" style={{ left: `${zero}%` }} />
                <div
                  className={`absolute inset-y-0.5 transition-opacity ${up ? "rounded-r bg-up" : "rounded-l bg-down"} ${
                    hover && hover !== s.key ? "opacity-40" : ""
                  }`}
                  style={up ? { left: `${zero}%`, width } : { right: `${100 - zero}%`, width }}
                />
              </div>
              <span className="num text-left font-medium text-ink">
                <span aria-hidden="true" className={`me-1 text-[0.7em] ${up ? "text-up" : "text-down"}`}>
                  {up ? "▲" : "▼"}
                </span>
                {fmtDelta(s.amount)}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex items-center justify-between border-t border-border/70 pt-2 text-xs">
        <span className="font-medium">סה״כ הפרש בנטו</span>
        <span className="num font-bold">{fmtDelta(total)}</span>
      </div>
    </figure>
  );
}
