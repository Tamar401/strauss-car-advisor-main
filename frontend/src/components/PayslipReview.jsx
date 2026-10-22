import { useState } from "react";

import { Button, Card, Input } from "../design/components";

const FIELDS = [
  ["base_salary", "שכר בסיס חודשי", "₪"],
  ["commissions", "עמלות חודשיות", "₪"],
  ["bonus", "בונוס חודשי", "₪"],
  ["pension_pct", "הפרשת עובד לפנסיה", "%"],
  ["study_fund_pct", "הפרשת עובד לקרן השתלמות", "%"],
  ["credit_points", "נקודות זיכוי", ""],
];

export default function PayslipReview({ extraction, saving, error, onConfirm, onCancel }) {
  const available = FIELDS.filter(([key]) => extraction.fields[key] != null);
  const [values, setValues] = useState(() =>
    Object.fromEntries(available.map(([key]) => [key, String(extraction.fields[key])])),
  );

  function update(key, value) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function submit(event) {
    event.preventDefault();
    const fields = Object.fromEntries(
      Object.entries(values)
        .filter(([, value]) => value.trim() !== "")
        .map(([key, value]) => [key, Number(value)]),
    );
    onConfirm(fields);
  }

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center overflow-y-auto bg-ink/45 p-4" role="presentation">
      <Card
        className="my-auto w-full max-w-xl bg-surface shadow-lift"
        role="dialog"
        aria-modal="true"
        aria-labelledby="payslip-review-title"
      >
        <h2 id="payslip-review-title" className="font-display text-xl font-bold">בדיקת נתונים מהתלוש</h2>
        <p className="mt-2 text-sm text-ink-soft">
          בדקו ותקנו את הערכים לפני השמירה. שדות שלא זוהו בבירור נשארו ריקים ולא יישמרו.
        </p>
        {available.length ? (
          <form onSubmit={submit} className="mt-5 space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              {available.map(([key, label, unit]) => (
                <Input
                  key={key}
                  label={unit ? `${label} (${unit})` : label}
                  type="number"
                  step="any"
                  min="0"
                  max={key.endsWith("_pct") ? "30" : undefined}
                  value={values[key]}
                  onChange={(event) => update(key, event.target.value)}
                />
              ))}
            </div>
            <p className="text-xs text-ink-soft">
              קובץ המקור אינו נשמר. הנתונים יישמרו בפרופיל רק לאחר אישור, ויסומנו כנתוני תלוש.
            </p>
            {error && <p role="alert" className="text-sm text-down">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={onCancel}>ביטול</Button>
              <Button type="submit" disabled={saving || Object.values(values).every((value) => value.trim() === "")}>
                {saving ? "שומר…" : "אישור ושמירה"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="mt-5 space-y-4">
            <p className="text-sm text-warn">לא זוהו נתונים שאפשר לאשר. אפשר להזין אותם ידנית בפרופיל.</p>
            {error && <p role="alert" className="text-sm text-down">{error}</p>}
            <div className="flex justify-end">
              <Button type="button" variant="ghost" onClick={onCancel}>סגירה</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
