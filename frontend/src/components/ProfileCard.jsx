// כרטיס הפרופיל — מה הבוט יודע, מאיפה כל נתון הגיע, ותיקון ישיר (דרישה בהנחיות). בעלות: מפתחת ב'.
import { useEffect, useState } from "react";

import { api } from "../api";
import { Button, Card, Input, SourceBadge } from "../design/components";

const FIELDS = [
  ["occupation", "עיסוק"],
  ["base_salary", "שכר בסיס", "₪"],
  ["commissions", "עמלות", "₪"],
  ["bonus", "בונוס", "₪"],
  ["pension_pct", "פנסיה", "%"],
  ["study_fund_pct", "קרן השתלמות", "%"],
  ["credit_points", "נקודות זיכוי"],
];

function show(value, unit) {
  if (value == null) return "—";
  if (typeof value === "number") {
    const n = value.toLocaleString("he-IL", { maximumFractionDigits: 2 });
    return unit === "₪" ? `${n} ₪` : unit === "%" ? `${n}%` : n;
  }
  return value;
}

function currentText(option, catalog) {
  if (!option) return null;
  if (option.kind === "waiver") return "ויתור (אחזקת רכב)";
  // רכב מהקטלוג, רכב מהמאגר (vou_key), או רכב שעוד לא זוהה — vehicle_label מכסה את שני האחרונים
  const car = option.car_id ? catalog[option.car_id] : null;
  const name = car ? `${car.model} (${car.registration_year})` : option.vehicle_label ?? option.car_id ?? "רכב";
  const part = option.participation?.value;
  return part != null ? `${name} · השתתפות ${part.toLocaleString("he-IL")} ₪` : name;
}

function Row({ label, value, source }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5">
      <span className="text-ink-soft">{label}</span>
      <span className="flex items-center gap-2 text-left">
        <span className="num font-medium">{value}</span>
        <SourceBadge source={source} />
      </span>
    </div>
  );
}

function EditForm({ state, onSaved, onCancel }) {
  const p = state.profile;
  const current = p.current_option?.value;
  const hasCar = current?.kind === "car";
  const [occupations, setOccupations] = useState([]);
  const [values, setValues] = useState(() => ({
    ...Object.fromEntries(FIELDS.map(([k]) => [k, p[k]?.value ?? ""])),
    children_under_23: p.children_under_23?.value ?? "",
    current_participation: hasCar ? current.participation?.value ?? "" : "",
  }));
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.occupations().then(setOccupations);
  }, []);

  const set = (k) => (e) => setValues({ ...values, [k]: e.target.value });

  async function save(e) {
    e.preventDefault();
    // שולחים רק מה שהשתנה — כך ההודעה בשיחה אומרת בדיוק מה תוקן
    const fields = {};
    for (const [k] of [...FIELDS, ["children_under_23"]]) {
      const before = k === "children_under_23" ? p.children_under_23?.value : p[k]?.value;
      const raw = values[k];
      if (raw === "" || raw == null) continue;
      const value = k === "occupation" ? raw : Number(raw);
      if (value !== before) fields[k] = value;
    }
    const part = values.current_participation === "" ? null : Number(values.current_participation);
    const partChanged = hasCar && part != null && part !== current.participation?.value;
    if (!Object.keys(fields).length && !partChanged) return onCancel();

    setSaving(true);
    setError(null);
    try {
      onSaved(await api.correctProfile(state.conversation_id, fields, partChanged ? part : null));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-3 text-sm">
      <label className="block">
        <span className="mb-1.5 block font-medium">עיסוק</span>
        <select
          value={values.occupation}
          onChange={set("occupation")}
          className="w-full rounded-2xl border border-border bg-surface px-4 py-2.5 outline-none focus:border-brand"
        >
          <option value="">—</option>
          {occupations.map((o) => (
            <option key={o.name} value={o.name}>
              {o.name} (קבוצה {o.group})
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-3">
        {FIELDS.slice(1).map(([k, label, unit]) => (
          <Input key={k} label={`${label}${unit ? ` (${unit})` : ""}`} type="number" step="any" min="0" value={values[k]} onChange={set(k)} />
        ))}
        <Input label="ילדים עד 23" type="number" min="0" value={values.children_under_23} onChange={set("children_under_23")} />
        {hasCar && (
          <Input label="השתתפות היום (₪)" type="number" min="0" value={values.current_participation} onChange={set("current_participation")} />
        )}
      </div>
      {error && <div className="text-down">{error}</div>}
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "שומר…" : "שמירה וחישוב מחדש"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          ביטול
        </Button>
      </div>
    </form>
  );
}

export default function ProfileCard({ state, catalog, onUpdated }) {
  const [editing, setEditing] = useState(false);
  const p = state.profile;
  const current = p.current_option?.value;
  const known = FIELDS.filter(([key]) => p[key]?.value != null).length + (current ? 1 : 0);
  const total = FIELDS.length + 1;

  return (
    <Card className="glass">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="font-display font-bold">
          מה אני יודע עליך{state.employee_display_name ? `, ${state.employee_display_name}` : ""}
        </div>
        <div className="flex items-center gap-2">
          <span className="num text-xs text-ink-soft">
            {known}/{total}
          </span>
          {!editing && (
            <Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => setEditing(true)}>
              ✎ תיקון
            </Button>
          )}
        </div>
      </div>
      {/* פס התקדמות: כמה מהנתונים הדרושים כבר נאספו */}
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="petal-ribbon h-full transition-all duration-500" style={{ width: `${(known / total) * 100}%` }} />
      </div>
      {editing ? (
        <EditForm
          state={state}
          onCancel={() => setEditing(false)}
          onSaved={(next) => {
            setEditing(false);
            onUpdated?.(next);
          }}
        />
      ) : (
        <div className="grid text-sm xl:grid-cols-2 xl:gap-x-10">
          {FIELDS.map(([key, label, unit]) => (
            <Row key={key} label={label} value={show(p[key]?.value, unit)} source={p[key]?.source ?? "missing"} />
          ))}
          <Row label="היום" value={currentText(current, catalog) ?? "—"} source={current ? p.current_option.source : "missing"} />
          {p.children_under_23?.value != null && (
            <Row label="ילדים עד 23" value={p.children_under_23.value} source={p.children_under_23.source} />
          )}
        </div>
      )}
    </Card>
  );
}
