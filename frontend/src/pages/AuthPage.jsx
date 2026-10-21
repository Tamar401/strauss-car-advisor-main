import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { Button, Card, Input, PetalMark } from "../design/components";

export default function AuthPage({ mode }) {
  const { user, checking, establishSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [setupCode, setSetupCode] = useState("");
  const [registrationCode, setRegistrationCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [mobileNumber, setMobileNumber] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (user) navigate(user.role === "admin" ? "/admin" : user.role === "rep" ? "/rep" : "/employee", { replace: true });
  }, [user, navigate]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      if (mode === "employee-register") {
        const session = await api.registerEmployee(email, password, fullName, mobileNumber);
        establishSession(session);
        navigate("/employee", { replace: true });
        return;
      }
      if (mode === "rep-register") {
        await api.registerRepresentative(email, password, registrationCode);
        navigate("/rep/login", { replace: true, state: { registrationComplete: true } });
        return;
      }
      const session = mode === "set-password"
        ? await api.setEmployeePassword(email, setupCode, password)
        : await api.login(email, password);
      if (mode === "rep-login" && session.user.role !== "rep") {
        setError("לחשבון הזה אין הרשאת נציג. יש להשתמש בפרטי חשבון נציג.");
        return;
      }
      if (mode === "admin-login" && session.user.role !== "admin") {
        setError("לחשבון הזה אין הרשאת מנהל/ת.");
        return;
      }
      establishSession(session);
      navigate(session.user.role === "admin" ? "/admin" : session.user.role === "rep" ? "/rep" : "/employee", { replace: true });
    } catch (err) {
      if (err.status === 401 && mode === "set-password") {
        setError("שם המשתמש או קוד ההפעלה אינם נכונים או שכבר נוצלו.");
      } else if (err.status === 422 && mode === "set-password") {
        setError("בחרו סיסמה באורך 12 תווים לפחות ובדקו את כתובת הדוא״ל.");
      } else if (err.status === 401 && mode === "rep-register") {
        setError("קוד ההרשמה אינו נכון, פג תוקפו או שכבר נוצל.");
      } else if (err.status === 422 && (mode === "employee-register" || mode === "rep-register")) {
        setError("בדקו את הפרטים ובחרו סיסמה באורך 12 תווים לפחות.");
      } else if (err.status === 401) {
        setError("פרטי הכניסה אינם נכונים. בדקו את שם המשתמש והסיסמה ונסו שוב.");
      } else {
        setError(err.message);
      }
    } finally {
      setPending(false);
    }
  }

  if (checking) return null;

  if (mode === "welcome") {
    return (
      <div className="mx-auto mt-8 max-w-lg">
        <Card className="glass text-center">
          <PetalMark size={60} className="mx-auto" />
          <h1 className="mt-4 font-display text-3xl font-bold">ברוכים הבאים ליועץ הרכב</h1>
          <p className="mt-3 text-ink-soft">התחברו לחשבון העובד שלכם כדי לצפות בשיחות ובשאלות.</p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button onClick={() => navigate("/login")}>כניסת עובד/ת</Button>
            <Button variant="secondary" onClick={() => navigate("/employee/register")}>הרשמת עובד/ת</Button>
            <Button variant="ghost" onClick={() => navigate("/rep/login")}>כניסת נציג/ת תחבורה</Button>
            <Button variant="ghost" onClick={() => navigate("/rep/register")}>הרשמת נציג/ת תחבורה</Button>
            <Button variant="ghost" onClick={() => navigate("/admin/login")}>כניסת מנהל/ת</Button>
          </div>
        </Card>
      </div>
    );
  }

  if (mode === "set-password") {
    return (
      <div className="mx-auto mt-8 max-w-sm">
        <Card className="glass border-t-4 border-t-brand p-8">
          <div className="text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-soft text-2xl text-brand" aria-hidden="true">
              +
            </div>
            <h1 className="mt-4 font-display text-2xl font-bold">הגדרת סיסמה</h1>
            <p className="mt-1 text-sm text-ink-soft">הזינו את כתובת הדוא״ל, קוד ההפעלה בן 5 הספרות שקיבלתם מהמנהל/ת, ובחרו סיסמה.</p>
          </div>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <Input
              label="שם משתמש (דוא״ל)"
              type="email"
              autoComplete="email"
              required
              maxLength={254}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Input
              label="קוד הפעלה"
              type="text"
              inputMode="numeric"
              pattern="[0-9]{5}"
              autoComplete="one-time-code"
              required
              minLength={5}
              maxLength={5}
              value={setupCode}
              onChange={(event) => setSetupCode(event.target.value)}
            />
            <div className="relative">
              <Input
                label="סיסמה חדשה"
                className="[&>input]:pe-12"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "הסתרת סיסמה" : "הצגת סיסמה"}
                aria-pressed={showPassword}
                className="absolute end-3 top-[2.35rem] rounded-full p-1 text-ink-soft transition hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
                  <circle cx="12" cy="12" r="3" />
                  {showPassword && <path d="m3 3 18 18" />}
                </svg>
              </button>
            </div>
            {error && <p role="alert" className="text-sm text-down">{error}</p>}
            <Button type="submit" disabled={pending} className="w-full">
              {pending ? "ממתינים..." : "שמירת סיסמה"}
            </Button>
          </form>
          <p className="mt-5 text-center text-sm text-ink-soft">
            <Link className="font-medium text-brand underline" to="/login">כבר הגדרתם סיסמה? חזרה לכניסה</Link>
          </p>
        </Card>
      </div>
    );
  }

  const isEmployeeRegistration = mode === "employee-register";
  const isRepresentativeRegistration = mode === "rep-register";
  const isRegistration = isEmployeeRegistration || isRepresentativeRegistration;

  return (
    <div className="mx-auto mt-12 max-w-sm">
      <Card className="glass border-t-4 border-t-brand p-8">
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-soft text-2xl text-brand" aria-hidden="true">
            {mode === "rep-login" ? "♙" : "↪"}
          </div>
          <h1 className="mt-4 font-display text-2xl font-bold">
            {isEmployeeRegistration
              ? "הרשמת עובד/ת"
              : isRepresentativeRegistration
                ? "הרשמת נציג/ת תחבורה"
                : mode === "rep-login"
                  ? "כניסת נציגים"
                  : mode === "admin-login"
                    ? "כניסת מנהל/ת"
                    : "ברוכים השבים"}
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            {isEmployeeRegistration
              ? "הזינו את כתובת הדוא״ל, השם המלא ובחרו סיסמה."
              : isRepresentativeRegistration
                ? "הזינו את כתובת הדוא״ל וקוד ההרשמה שקיבלתם ממנהל/ת המערכת, ובחרו סיסמה."
                : mode === "rep-login"
              ? "התחברו לחשבון הנציג האישי שלכם."
              : mode === "admin-login"
                ? "התחברו לניהול חשבונות נציגים ולהגדרות המערכת."
                : "התחברו כדי להמשיך לשיחות שלכם."}
          </p>
        </div>
        <form onSubmit={submit} className="mt-6 space-y-4">
          {isEmployeeRegistration && (
            <Input
              label="שם מלא"
              type="text"
              autoComplete="name"
              required
              minLength={1}
              maxLength={100}
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          )}
          {isEmployeeRegistration && (
            <Input
              label="מספר טלפון (לא חובה)"
              type="tel"
              autoComplete="tel"
              dir="ltr"
              maxLength={32}
              value={mobileNumber}
              onChange={(event) => setMobileNumber(event.target.value)}
            />
          )}
          <Input
            label="שם משתמש (דוא״ל)"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          {isRepresentativeRegistration && (
            <Input
              label="קוד הרשמה חד-פעמי"
              type="text"
              autoComplete="one-time-code"
              required
              minLength={40}
              maxLength={64}
              value={registrationCode}
              onChange={(event) => setRegistrationCode(event.target.value)}
            />
          )}
          <div className="relative">
            <Input
              label="סיסמה"
              className="[&>input]:pe-12"
              type={showPassword ? "text" : "password"}
              autoComplete={isRegistration ? "new-password" : "current-password"}
              required
              minLength={isRegistration ? 12 : 1}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              type="button"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "הסתרת סיסמה" : "הצגת סיסמה"}
              aria-pressed={showPassword}
              className="absolute end-3 top-[2.35rem] rounded-full p-1 text-ink-soft transition hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
                <circle cx="12" cy="12" r="3" />
                {showPassword && <path d="m3 3 18 18" />}
              </svg>
            </button>
          </div>
          {error && <p role="alert" className="text-sm text-down">{error}</p>}
          {mode === "rep-login" && location.state?.registrationComplete && (
            <p role="status" className="text-sm text-up">ההרשמה הושלמה. כעת אפשר להתחבר עם כתובת הדוא״ל והסיסמה שבחרתם.</p>
          )}
          <Button type="submit" disabled={pending} className="w-full">
            {pending
              ? "ממתינים..."
              : isEmployeeRegistration
                ? "הרשמה"
                : isRepresentativeRegistration
                  ? "הפעלת חשבון נציג"
                  : "Log in"}
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-ink-soft">
          {isRepresentativeRegistration ? (
            <Link className="font-medium text-brand underline" to="/rep/login">כבר נרשמתם? כניסה לנציגים</Link>
          ) : isEmployeeRegistration ? (
            <Link className="font-medium text-brand underline" to="/login">כבר נרשמתם? כניסה לעובדים</Link>
          ) : mode === "rep-login" || mode === "admin-login" ? (
            mode === "rep-login"
              ? <Link className="font-medium text-brand underline" to="/rep/register">יש לכם קוד הרשמה? הירשמו כנציגים</Link>
              : "הכניסה למנהל/ת נפרדת מחשבונות עובדים ונציגים."
          ) : (
            <Link className="font-medium text-brand underline" to="/employee/register">חדשים במערכת? הרשמת עובד/ת</Link>
          )}
        </p>
      </Card>
    </div>
  );
}
