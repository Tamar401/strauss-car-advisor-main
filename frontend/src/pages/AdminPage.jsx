import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { Button, Card, Input, Notice } from "../design/components";

export default function AdminPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [invitation, setInvitation] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function invite(event) {
    event.preventDefault();
    setPending(true);
    setInvitation(null);
    setError("");
    try {
      setInvitation(await api.createRepInvitation(email, fullName, mobile));
      setFullName("");
      setEmail("");
      setMobile("");
    } catch (err) {
      setError(err.status === 409 ? "כבר קיים חשבון עם הדוא״ל הזה." : err.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <section>
        <h1 className="font-display text-3xl font-bold">ניהול נציגים</h1>
        <p className="mt-2 text-ink-soft">
          נציגי תחבורה רואים את השאלות של כל העובדים, ולכן נרשמים רק בהזמנה: מנפיקים קוד בן 5 ספרות, הקשור לדוא״ל
          ותקף ל-24 שעות, והנציג/ה נרשם/ת איתו ובוחר/ת סיסמה. הזמנה חוזרת לאותו דוא״ל מחליפה את הקוד הקודם.
          עובדים נרשמים לבד.
        </p>
        <Link className="mt-2 inline-block text-sm font-medium text-brand underline" to="/rules">
          מעבר לכללי המערכת
        </Link>
      </section>

      <Card className="glass">
        <h2 className="font-display text-xl font-bold">הזמנת נציג/ת תחבורה</h2>
        <form onSubmit={invite} className="mt-4 space-y-4">
          <Input
            label="שם מלא"
            autoComplete="name"
            required
            maxLength={100}
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
          <Input
            label="דוא״ל"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Input
            label="מספר טלפון (לא חובה)"
            type="tel"
            autoComplete="tel"
            dir="ltr"
            maxLength={32}
            value={mobile}
            onChange={(event) => setMobile(event.target.value)}
          />
          {error && <p role="alert" className="text-sm text-down">{error}</p>}
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? "יוצר קוד…" : "יצירת קוד הרשמה"}
          </Button>
        </form>
        {invitation && (
          <Notice tone="brand">
            <p className="font-medium">
              קוד הרשמה עבור <bdi dir="ltr">{invitation.email}</bdi>
            </p>
            <bdi dir="ltr" className="mt-2 block select-all rounded-xl bg-surface px-3 py-2 text-center font-mono text-2xl tracking-[0.4em]">
              {invitation.code}
            </bdi>
            <p className="mt-2 text-xs">
              תקף עד {new Date(invitation.expires_at).toLocaleString("he-IL")}. הקוד מוצג פעם אחת בלבד, מסרו אותו בערוץ
              מאובטח. ההרשמה בעמוד{" "}
              <Link className="font-medium underline" to="/rep/register">הרשמת נציגים</Link>.
            </p>
          </Notice>
        )}
      </Card>
    </div>
  );
}
