// שער קוד גישה למסכי הנציג והכללים. הבדיקה האמיתית בשרת — כאן רק חוויית הכניסה.
import { useEffect, useState } from "react";

import { api, getAccessCode, setAccessCode } from "../api";
import { Button, Card, Input, PetalMark } from "../design/components";

const TITLES = { rep: "מסך נציג התחבורה", admin: "מסך הכללים" };

export default function AccessGate({ role, children }) {
  const [state, setState] = useState("checking"); // checking | locked | open
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);

  async function tryCode(value) {
    try {
      await api.checkAccess(role, value ?? "");
      if (value) setAccessCode(value);
      setState("open");
      return true;
    } catch {
      return false;
    }
  }

  // קוד שכבר הוקלד בלשונית הזו, או שרת במצב פיתוח פתוח — נכנסים בלי לשאול
  useEffect(() => {
    tryCode(getAccessCode()).then((ok) => !ok && setState("locked"));
  }, [role]);

  async function submit(e) {
    e.preventDefault();
    setError(null);
    if (!(await tryCode(code.trim()))) setError("קוד שגוי");
  }

  if (state === "open") return children;
  if (state === "checking") return null;

  return (
    <div className="mx-auto mt-10 max-w-sm">
      <Card className="glass text-center">
        <PetalMark size={44} className="mx-auto" />
        <h1 className="mt-3 font-display text-xl font-bold">{TITLES[role]}</h1>
        <p className="mt-1 text-sm text-ink-soft">המסך מוגן — יש להקליד קוד גישה</p>
        <form onSubmit={submit} className="mt-5 space-y-3 text-right">
          <Input label="קוד גישה" type="password" autoFocus value={code} onChange={(e) => setCode(e.target.value)} />
          {error && <div className="text-sm text-down">{error}</div>}
          <Button type="submit" className="w-full">
            כניסה
          </Button>
        </form>
      </Card>
    </div>
  );
}
