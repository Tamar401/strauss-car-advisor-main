// רשת כרטיסי ההשוואה, עם סינון כשיש הרבה חלופות. בעלות: מפתחת א'.
// חלופות לא זמינות מקופלות בסוף — הן לא נעלמות (העובד רואה גם למה לא), אבל לא מסתירות את מה שכן אפשר.
import { useState } from "react";

import OptionCard from "./OptionCard";

const FILTERS = [
  { key: "all", label: "הכל", test: () => true },
  { key: "electric", label: "⚡ חשמליים", test: (a) => a.car?.drive === "electric" },
  { key: "hybrid", label: "🍃 היברידיים ופלאג-אין", test: (a) => ["hybrid", "plugin"].includes(a.car?.drive) },
  { key: "waiver", label: "💰 ויתור", test: (a) => a.option.kind === "waiver" },
];

export default function ComparisonGrid({ comparison }) {
  const [filter, setFilter] = useState("all");
  const many = comparison.alternatives.length > 4;
  const test = FILTERS.find((f) => f.key === filter).test;

  const shown = comparison.alternatives.filter((a) => a.status !== "blocked" && test(a));
  const blocked = comparison.alternatives.filter((a) => a.status === "blocked" && test(a));

  return (
    <div className="space-y-4">
      {many && (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="סינון חלופות">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              aria-pressed={filter === f.key}
              className={`rounded-full px-3 py-1 text-xs transition ${
                filter === f.key ? "bg-ink font-medium text-surface" : "bg-muted text-ink-soft hover:text-ink"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <OptionCard result={comparison.current} isCurrent />
        {shown.map((a, i) => (
          <OptionCard key={`${a.option.kind}-${a.option.car_id ?? ""}-${i}`} result={a} current={comparison.current} />
        ))}
      </div>

      {blocked.length > 0 &&
        (many ? (
          <details className="rounded-2xl border border-border/70 bg-surface/60 p-4">
            <summary className="cursor-pointer text-sm font-medium text-ink-soft">
              {blocked.length} אפשרויות לא זמינות לך — ולמה
            </summary>
            <ul className="mt-3 space-y-2 text-sm">
              {blocked.map((a, i) => (
                <li key={i} className="flex flex-wrap gap-x-2">
                  <bdi className="font-medium">{a.car ? `${a.car.model} (${a.car.registration_year})` : a.label}</bdi>
                  <span className="text-ink-soft">{a.eligibility.reason_text}</span>
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {blocked.map((a, i) => (
              <OptionCard key={i} result={a} current={comparison.current} />
            ))}
          </div>
        ))}
    </div>
  );
}
