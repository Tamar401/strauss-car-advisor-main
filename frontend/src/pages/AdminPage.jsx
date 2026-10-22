import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { Button, Card, Input, Notice } from "../design/components";

export default function AdminPage() {
  const [email, setEmail] = useState("");
  const [activation, setActivation] = useState(null);
  const [employeeEmail, setEmployeeEmail] = useState("");
  const [employeeName, setEmployeeName] = useState("");
  const [employeeMobile, setEmployeeMobile] = useState("");
  const [employeeActivation, setEmployeeActivation] = useState(null);
  const [error, setError] = useState("");
  const [employeeError, setEmployeeError] = useState("");
  const [pending, setPending] = useState(false);
  const [employeePending, setEmployeePending] = useState(false);

  async function createActivation(event) {
    event.preventDefault();
    setPending(true);
    setActivation(null);
    setError("");
    try {
      setActivation(await api.createRepresentativeActivation(email));
      setEmail("");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  async function createEmployeeActivation(event) {
    event.preventDefault();
    setEmployeePending(true);
    setEmployeeActivation(null);
    setEmployeeError("");
    try {
      setEmployeeActivation(await api.createEmployeeActivation(employeeEmail, employeeName, employeeMobile));
      setEmployeeEmail("");
      setEmployeeName("");
      setEmployeeMobile("");
    } catch (err) {
      setEmployeeError(err.message);
    } finally {
      setEmployeePending(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <section>
        <h1 className="font-display text-3xl font-bold">ניהול חשבונות נציגים</h1>
        <p className="mt-2 text-ink-soft">
          יצירת קוד הרשמה חד-פעמי לנציג/ת תחבורה. הנציג/ה יבחר/תבחר סיסמה בהרשמה.
        </p>
        <Link className="mt-2 inline-block text-sm font-medium text-brand underline" to="/rules">
          מעבר לכללי המערכת
        </Link>
      </section>

      <Card className="glass">
        <h2 className="font-display text-xl font-bold">הזמנת נציג/ת תחבורה</h2>
        <form onSubmit={createActivation} className="mt-4 space-y-4">
          <Input
            label="שם משתמש (דוא״ל)"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          {error && <p role="alert" className="text-sm text-down">{error}</p>}
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? "יוצר קוד..." : "יצירת קוד הרשמה"}
          </Button>
        </form>
        {activation && (
          <Notice tone="brand">
            <p className="font-medium">קוד הרשמה נוצר עבור <bdi dir="ltr">{activation.email}</bdi></p>
            <p className="mt-2 text-xs">תקף עד {new Date(activation.expires_at).toLocaleString()}</p>
            <bdi
              dir="ltr"
              className="mt-2 block select-all break-all rounded-xl bg-surface px-3 py-2 font-mono text-sm"
            >
              {activation.registration_code}
            </bdi>
            <p className="mt-2 text-xs">
              מסרו את הקוד לנציג/ה בערוץ מאובטח. הרשמה תתאפשר בעמוד
              {" "}<Link className="font-medium underline" to="/rep/register">הרשמת נציגים</Link>.
            </p>
          </Notice>
        )}
      </Card>

      <Card className="glass">
        <h2 className="font-display text-xl font-bold">הזמנת עובד/ת עם קוד הפעלה</h2>
        <p className="mt-2 text-sm text-ink-soft">
          הקוד קשור לדוא״ל, תקף ל־24 שעות ונועד להגדרת סיסמה ראשונה. אפשר להנפיק קוד חדש אם פג תוקפו.
        </p>
        <form onSubmit={createEmployeeActivation} className="mt-4 space-y-4">
          <Input
            label="שם מלא"
            autoComplete="name"
            required
            maxLength={100}
            value={employeeName}
            onChange={(event) => setEmployeeName(event.target.value)}
          />
          <Input
            label="כתובת דוא״ל"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            value={employeeEmail}
            onChange={(event) => setEmployeeEmail(event.target.value)}
          />
          <Input
            label="מספר טלפון (לא חובה)"
            type="tel"
            autoComplete="tel"
            dir="ltr"
            maxLength={32}
            value={employeeMobile}
            onChange={(event) => setEmployeeMobile(event.target.value)}
          />
          {employeeError && <p role="alert" className="text-sm text-down">{employeeError}</p>}
          <Button type="submit" disabled={employeePending} className="w-full">
            {employeePending ? "יוצר קוד…" : "יצירת קוד לעובד/ת"}
          </Button>
        </form>
        {employeeActivation && (
          <Notice tone="brand">
            <p className="font-medium">קוד הפעלה נוצר עבור <bdi dir="ltr">{employeeActivation.email}</bdi></p>
            <p className="mt-2 text-xs">תקף עד {new Date(employeeActivation.expires_at).toLocaleString()}</p>
            <bdi dir="ltr" className="mt-2 block select-all break-all rounded-xl bg-surface px-3 py-2 font-mono text-lg">
              {employeeActivation.setup_code}
            </bdi>
            <p className="mt-2 text-xs">יש למסור לעובד/ת בערוץ מאובטח. הקוד יוצג פעם אחת בלבד.</p>
          </Notice>
        )}
      </Card>
    </div>
  );
}
