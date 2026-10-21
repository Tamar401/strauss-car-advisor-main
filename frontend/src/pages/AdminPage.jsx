import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { Button, Card, Input, Notice } from "../design/components";

export default function AdminPage() {
  const [email, setEmail] = useState("");
  const [activation, setActivation] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

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
    </div>
  );
}
