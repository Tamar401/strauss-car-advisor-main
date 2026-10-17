// עמוד הייחוס של מערכת העיצוב. כל רכיב חדש ב-design/components.jsx מקבל כאן דוגמה.
import { useEffect, useState } from "react";

import { api } from "../api";
import OptionCard from "../components/OptionCard";
import {
  Badge,
  Button,
  Card,
  ChatBubble,
  Delta,
  Input,
  Notice,
  SectionTitle,
  SourceBadge,
  Stat,
  StatusBadge,
} from "../design/components";

const SWATCHES = ["brand", "accent", "up", "down", "warn", "ink", "ink-soft", "muted", "surface", "border"];
const PETALS = ["red", "orange", "yellow", "lime", "green", "teal", "blue"];

export default function DesignPage() {
  const [comparison, setComparison] = useState(null);
  useEffect(() => {
    api.demoCompare("E-001").then(setComparison);
  }, []);

  return (
    <div className="space-y-8">
      <section>
        <SectionTitle hint="tokens.css · מתחלפים אוטומטית במצב כהה">צבעים</SectionTitle>
        <div className="flex flex-wrap gap-3">
          {SWATCHES.map((s) => (
            <div key={s} className="text-center text-xs">
              <div className={`h-12 w-16 rounded-xl border border-border bg-${s}`} />
              <div className="mt-1 text-ink-soft">{s}</div>
            </div>
          ))}
        </div>
        <div className="mt-5 text-sm font-medium">עלי הכותרת · סוגי הנעה וקישוטים</div>
        <div className="mt-2 flex flex-wrap gap-3">
          {PETALS.map((p) => (
            <div key={p} className="text-center text-xs">
              <div className={`h-12 w-12 rounded-full bg-petal-${p}`} />
              <div className="mt-1 text-ink-soft">{p}</div>
            </div>
          ))}
        </div>
        <div className="petal-ribbon mt-4 h-2 rounded-full" />
      </section>

      <section>
        <SectionTitle>טיפוגרפיה</SectionTitle>
        <Card className="space-y-2">
          <div className="font-display text-2xl font-bold">כותרת ראשית · Rubik</div>
          <div className="font-display text-lg font-bold">כותרת משנית</div>
          <p className="text-sm">טקסט גוף · Heebo. מספרים תמיד עם המחלקה num: <span className="num">11,032 ₪</span></p>
        </Card>
      </section>

      <section>
        <SectionTitle>רכיבים</SectionTitle>
        <Card className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <Button>פעולה ראשית</Button>
            <Button variant="secondary">משנית</Button>
            <Button variant="ghost">שקטה</Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge>ניטרלי</Badge>
            <Badge tone="brand">מותג</Badge>
            <StatusBadge status="complete" />
            <StatusBadge status="partial" />
            <StatusBadge status="blocked" />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            מקור נתון:
            {["employee", "payslip", "rep", "catalog", "rules", "missing"].map((s) => (
              <SourceBadge key={s} source={s} />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-4">
            <Stat label="נטו היום" sub="לפני השינוי">
              <span className="num">11,032 ₪</span>
            </Stat>
            <Stat label="הפרש">
              <Delta value={661} size="lg" />
            </Stat>
            <Stat label="הפרש">
              <Delta value={-440} size="lg" />
            </Stat>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="שכר בסיס" hint="ברוטו חודשי" placeholder="14,200" />
            <Input label="נקודות זיכוי" placeholder="2.25" />
          </div>
          <Notice>חסר לי סכום ההשתתפות שלך ברכב החדש, ושלחתי שאלה לנציג התחבורה.</Notice>
          <div className="space-y-2 rounded-xl bg-muted p-4">
            <ChatBubble role="user">אני שוקלת לעבור לרכב חשמלי. כמה זה ישנה לי בנטו?</ChatBubble>
            <ChatBubble role="assistant">בכיף! נתחיל מהבסיס: באיזו קבוצת זכאות את/ה (א-ד)?</ChatBubble>
          </div>
        </Card>
      </section>

      {comparison && (
        <section>
          <SectionTitle hint="נתוני דמו · E-001">כרטיסי חלופה</SectionTitle>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <OptionCard result={comparison.current} isCurrent />
            {comparison.alternatives.map((a, i) => (
              <OptionCard key={i} result={a} current={comparison.current} receiptOpen={i === 0} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
