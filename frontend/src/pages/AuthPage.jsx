import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, setSessionToken } from "../api";
import { useAuth } from "../auth";
import { Button, Card, Input, PetalMark } from "../design/components";

// עובדים נרשמים לבד. נציגים רואים את השאלות של כל העובדים, ולכן נרשמים רק עם קוד מהמנהל/ת
const ROLES = {
  employee: {
    title: "עובד/ת",
    icon: "🚗",
    pitch: "כמה ישתנה הנטו שלי אם אחליף רכב, אעבור לחשמלי או אוותר על הרכב?",
    login: "/login",
    register: "/employee/register",
    registerLabel: "הרשמה",
    home: "/employee",
  },
  rep: {
    title: "נציג/ת תחבורה",
    icon: "🧭",
    pitch: "מענה לשאלות פתוחות של עובדים. השיחה שלהם ממשיכה מאותה נקודה.",
    login: "/rep/login",
    register: "/rep/register",
    registerLabel: "הרשמה עם קוד",
    home: "/rep",
  },
  admin: {
    title: "מנהל/ת",
    icon: "⚙️",
    pitch: "הזמנת נציגי תחבורה וניהול כללי המערכת.",
    login: "/admin/login",
    home: "/admin",
  },
};

const MODES = {
  login: { role: "employee", register: false },
  "employee-register": { role: "employee", register: true },
  "rep-login": { role: "rep", register: false },
  "rep-register": { role: "rep", register: true },
  "admin-login": { role: "admin", register: false },
};

function homeFor(role) {
  return ROLES[role]?.home ?? "/employee";
}

function Welcome() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto mt-6 max-w-5xl">
      <div className="text-center">
        <PetalMark size={56} className="mx-auto" />
        <h1 className="mt-4 font-display text-3xl font-bold sm:text-4xl">ברוכים הבאים ליועץ הרכב</h1>
        <p className="mt-2 text-ink-soft">בחרו איך אתם נכנסים. נציגי תחבורה נרשמים עם קוד שמקבלים מהמנהל/ת.</p>
      </div>
      <div className="mt-8 grid gap-5 md:grid-cols-3">
        {Object.entries(ROLES).map(([role, r]) => (
          <Card key={role} className="glass flex flex-col p-6">
            <div className="flex items-center gap-3">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-soft text-2xl" aria-hidden="true">
                {r.icon}
              </span>
              <h2 className="font-display text-xl font-bold">{r.title}</h2>
            </div>
            <p className="mt-3 flex-1 text-sm leading-relaxed text-ink-soft">{r.pitch}</p>
            <div className="mt-5 flex flex-col gap-2">
              <Button className="w-full" onClick={() => navigate(r.login)}>כניסה</Button>
              {r.register && (
                <Button variant="secondary" className="w-full" onClick={() => navigate(r.register)}>
                  {r.registerLabel}
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function PasswordInput({ value, onChange, isNew }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        label={isNew ? "בחירת סיסמה (12 תווים לפחות)" : "סיסמה"}
        className="[&>input]:pe-12"
        type={visible ? "text" : "password"}
        autoComplete={isNew ? "new-password" : "current-password"}
        required
        minLength={isNew ? 12 : 1}
        maxLength={128}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "הסתרת סיסמה" : "הצגת סיסמה"}
        aria-pressed={visible}
        className="absolute end-3 top-[2.35rem] rounded-full p-1 text-ink-soft transition hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {visible && <path d="m3 3 18 18" />}
        </svg>
      </button>
    </div>
  );
}

function errorText(err, register, role) {
  if (err.status === 503 && role === "admin") {
    return "כניסת מנהל/ת לא הוגדרה בשרת. יש להגדיר ADMIN_USERNAME (כתובת דוא״ל) ו-ADMIN_PASSWORD באורך 12 תווים לפחות ולהפעיל מחדש את השרת.";
  }
  if (register) {
    if (err.status === 401) return "הקוד אינו תקף, פג תוקפו או שכבר נוצל. ודאו שהדוא״ל זהה לזה שבהזמנה, או בקשו מהמנהל/ת קוד חדש.";
    if (err.status === 409) return "כבר קיים חשבון עם הדוא״ל הזה. אפשר להיכנס איתו.";
    if (err.status === 422) return role === "rep"
      ? "בדקו את הדוא״ל, הקוד (5 ספרות) ובחרו סיסמה באורך 12 תווים לפחות."
      : "בדקו את השם והדוא״ל, ובחרו סיסמה באורך 12 תווים לפחות.";
    if (err.status === 429) return "יותר מדי ניסיונות. נסו שוב בעוד 15 דקות.";
  }
  if (err.status === 401) return "פרטי הכניסה אינם נכונים. בדקו את הדוא״ל והסיסמה ונסו שוב.";
  return err.message;
}

export default function AuthPage({ mode }) {
  const { user, checking, establishSession } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (user) navigate(homeFor(user.role), { replace: true });
  }, [user, navigate]);

  if (checking) return null;
  if (mode === "welcome") return <Welcome />;

  const { role, register } = MODES[mode];
  const r = ROLES[role];

  async function submit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const session = !register
        ? await api.login(email, password, role === "admin" ? "admin" : undefined)
        : role === "rep"
          ? await api.registerRep(email, code, password)
          : await api.registerEmployee(email, password, fullName, mobile);
      if (session.user.role !== role) {
        // הכניסה הצליחה אבל לתפקיד אחר — סוגרים את ה-session בשרת בלי להיכנס, ומפנים לעמוד הנכון
        setSessionToken(session.access_token);
        try {
          await api.logout();
        } finally {
          setSessionToken(null);
        }
        setError(`החשבון הזה הוא של ${ROLES[session.user.role]?.title ?? session.user.role}. היכנסו מהעמוד המתאים.`);
        return;
      }
      establishSession(session);
      navigate(r.home, { replace: true });
    } catch (err) {
      setError(errorText(err, register, role));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <Card className="glass border-t-4 border-t-brand p-8">
        <div className="text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-brand-soft text-2xl" aria-hidden="true">
            {r.icon}
          </div>
          <h1 className="mt-4 font-display text-2xl font-bold">
            {register ? "הרשמה" : "כניסה"} · {r.title}
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            {!register
              ? "התחברו עם הדוא״ל והסיסמה שלכם."
              : role === "rep"
                ? "הזינו את הדוא״ל שאליו נשלחה ההזמנה ואת הקוד בן 5 הספרות שקיבלתם מהמנהל/ת, ובחרו סיסמה."
                : "פותחים חשבון בדקה, ואחר כך מתחילים לשאול."}
          </p>
        </div>
        <form onSubmit={submit} className="mt-6 space-y-4">
          {register && role === "employee" && (
            <Input
              label="שם מלא"
              autoComplete="name"
              required
              maxLength={100}
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          )}
          <Input
            label="דוא״ל"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          {register && role === "employee" && (
            <Input
              label="מספר טלפון (לא חובה)"
              type="tel"
              autoComplete="tel"
              dir="ltr"
              maxLength={32}
              value={mobile}
              onChange={(event) => setMobile(event.target.value)}
            />
          )}
          {register && role === "rep" && (
            <Input
              label="קוד הרשמה"
              type="text"
              inputMode="numeric"
              pattern="[0-9]{5}"
              autoComplete="one-time-code"
              required
              minLength={5}
              maxLength={5}
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            />
          )}
          <PasswordInput value={password} onChange={setPassword} isNew={register} />
          {error && <p role="alert" className="text-sm text-down">{error}</p>}
          <Button type="submit" disabled={pending} className="w-full">
            {pending ? "ממתינים..." : register ? "הרשמה" : "כניסה"}
          </Button>
        </form>
        <div className="mt-5 space-y-2 text-center text-sm text-ink-soft">
          {r.register && (
            <p>
              {register ? "כבר נרשמתם? " : role === "rep" ? "קיבלתם קוד מהמנהל/ת? " : "עוד אין לכם חשבון? "}
              <Link className="font-medium text-brand underline" to={register ? r.login : r.register}>
                {register ? "כניסה" : r.registerLabel}
              </Link>
            </p>
          )}
          <p>
            <Link className="underline" to="/welcome">חזרה לבחירת סוג הכניסה</Link>
          </p>
        </div>
      </Card>
    </div>
  );
}
