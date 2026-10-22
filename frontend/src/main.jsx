import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";

import "./design/tokens.css";
import { api, getSessionToken, setSessionToken } from "./api";
import { AuthProvider, useAuth } from "./auth";
import AdminPage from "./pages/AdminPage";
import AuthPage from "./pages/AuthPage";
import DesignPage from "./pages/DesignPage";
import EmployeePage from "./pages/EmployeePage";
import RepPage from "./pages/RepPage";
import RulesPage from "./pages/RulesPage";

const NAV = [
  { to: "/employee", label: "עובד" },
  { to: "/rep", label: "נציג תחבורה" },
  { to: "/admin", label: "ניהול נציגים" },
  { to: "/rules", label: "כללים" },
  // /design — דף ייחוס פנימי למפתחות, לא בתפריט. נכנסים בכתובת ישירה
];

/** פס הקשת מתחת לכותרת: מתמלא מימין לשמאל לפי מיקום הגלילה בדף */
function ScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      // אין מה לגלול → הדף כולו כבר על המסך, אז הפס מלא
      setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 1);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    // התוכן יכול לגדול בלי גלילה (הודעות בצ'אט, השוואה שנטענה) — מחשבים מחדש
    const observer = new ResizeObserver(onScroll);
    observer.observe(document.body);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="relative h-1 bg-border/60" role="progressbar" aria-label="התקדמות בדף" aria-valuenow={Math.round(progress * 100)}>
      {/* clip-path חושף את הקשת מימין לשמאל בלי למעוך את הצבעים */}
      <div className="petal-ribbon absolute inset-0" style={{ clipPath: `inset(0 0 0 ${(1 - progress) * 100}%)` }} />
    </div>
  );
}

function Shell() {
  const { user, checking, logout } = useAuth();
  return (
    <div className="aurora relative isolate min-h-screen">
      <header className="glass sticky top-0 z-10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <NavLink
            to="/"
            aria-label="דף הבית"
            className="flex items-center gap-3 rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          >
            <img src="/strauss-logo.svg" alt="שטראוס" className="h-11 w-auto" />
            <div className="h-9 w-px bg-border" />
            <div className="leading-tight">
              <div className="font-display text-lg font-bold">יועץ הרכב</div>
              <div className="text-xs text-ink-soft">מה יקרה לנטו שלי?</div>
            </div>
          </NavLink>
          <nav className="flex max-w-full gap-1 overflow-x-auto rounded-full bg-muted/80 p-1">
            {NAV.filter((n) => !["/admin", "/rules"].includes(n.to) || user?.role === "admin").map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-full px-4 py-1.5 text-sm transition ${
                    isActive ? "bg-surface font-medium text-brand shadow-card" : "text-ink-soft hover:text-ink"
                  }`
                }
              >
                {n.label}
              </NavLink>
            )            )}
          </nav>
          <div className="flex items-center gap-2">
            {user ? (
              <>
                <span className="hidden text-xs text-ink-soft sm:inline">{user.email}</span>
                <button className="rounded-full px-3 py-1.5 text-sm text-ink-soft hover:bg-muted" onClick={logout}>
                  Log out
                </button>
              </>
            ) : !checking ? (
              <NavLink className="rounded-full px-3 py-1.5 text-sm text-ink-soft hover:bg-muted" to="/login">
                Log in
              </NavLink>
            ) : null}
          </div>
        </div>
        <ScrollProgress />
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Navigate to={user ? "/employee" : "/welcome"} replace />} />
          <Route path="/welcome" element={<AuthPage mode="welcome" />} />
          <Route path="/register" element={<Navigate to="/employee/register" replace />} />
          <Route path="/employee/register" element={<AuthPage mode="employee-register" />} />
          <Route path="/set-password" element={<AuthPage mode="set-password" />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/rep/login" element={<AuthPage mode="rep-login" />} />
          <Route path="/rep/register" element={<AuthPage mode="rep-register" />} />
          <Route
            path="/employee"
            element={checking ? null : user?.role === "employee" ? <EmployeePage /> : user?.role === "rep" ? <Navigate to="/rep" replace /> : <Navigate to="/welcome" replace />}
          />
          <Route
            path="/rep"
            element={
              checking ? null : user?.role === "rep" ? <RepPage /> : user ? (
                <div className="mx-auto mt-10 max-w-sm rounded-3xl border border-border bg-surface p-6 text-center">
                  <p className="text-sm text-ink-soft">יש לצאת מחשבון העובד כדי להתחבר לחשבון נציג.</p>
                  <button className="mt-4 rounded-full bg-brand-soft px-4 py-2 text-sm font-medium text-brand" onClick={logout}>
                    יציאה והתחברות כנציג
                  </button>
                </div>
              ) : <AuthPage mode="rep-login" />
            }
          />
          <Route path="/admin/login" element={checking ? null : user?.role === "admin" ? <Navigate to="/admin" replace /> : <AuthPage mode="admin-login" />} />
          <Route path="/admin" element={checking ? null : user?.role === "admin" ? <AdminPage /> : <Navigate to="/admin/login" replace />} />
          <Route path="/rules" element={checking ? null : user?.role === "admin" ? <RulesPage /> : <Navigate to="/admin/login" replace />} />
          <Route path="/design" element={<DesignPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!getSessionToken()) {
      setChecking(false);
      return;
    }
    let active = true;
    api.currentUser()
      .then((current) => active && setUser(current))
      .catch((error) => {
        if (active && error.status === 401) setSessionToken(null);
      })
      .finally(() => active && setChecking(false));
    return () => {
      active = false;
    };
  }, []);

  function establishSession(session) {
    setSessionToken(session.access_token);
    setUser(session.user);
  }

  async function logout() {
    try {
      if (getSessionToken()) await api.logout();
    } finally {
      setSessionToken(null);
      setUser(null);
    }
  }

  return (
    <AuthProvider value={{ user, checking, establishSession, logout }}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </AuthProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
