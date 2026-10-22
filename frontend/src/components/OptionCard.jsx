// כרטיס חלופה — בעלות: מפתחת א'. כולל את גרף המפל ואת ה"קבלה" הנפתחת.
import { Card, Delta, DRIVE, DriveTag, Money, StatusBadge } from "../design/components";
import BreakEven from "./BreakEven";
import NetWaterfall from "./NetWaterfall";
import OptionFacts from "./OptionFacts";
import Receipt from "./Receipt";

export default function OptionCard({ result, current, isCurrent = false, receiptOpen = false }) {
  const drive = result.option.kind === "waiver" ? "waiver" : result.car?.drive ?? result.drive;
  const petal = DRIVE[drive]?.petal ?? "red";
  const blocked = result.status === "blocked";
  const complete = result.status === "complete" && !isCurrent;

  return (
    <Card interactive className={`relative overflow-hidden animate-rise ${blocked ? "opacity-70" : ""}`}>
      {/* פס צבע לפי סוג ההנעה */}
      <div className={`absolute inset-x-0 top-0 h-1.5 bg-petal-${petal}`} />
      {isCurrent && (
        <div className="absolute left-4 top-4 rounded-full bg-ink px-2.5 py-0.5 text-xs font-medium text-surface">היום</div>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <DriveTag drive={drive} />
        {!isCurrent && <StatusBadge status={result.status} />}
      </div>
      <div className="mt-2 font-display text-lg font-bold leading-snug">
        {/* שם רכב באנגלית — מבודד כדי שהשנה לא תקפוץ לצד הלא נכון בתוך RTL */}
        {result.car ? <bdi>{`${result.car.model} (${result.car.registration_year})`}</bdi> : result.label}
      </div>

      <div className="mt-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs text-ink-soft">נטו משוער</div>
          <Money value={result.net} className="font-display text-2xl font-bold" />
        </div>
        {/* delta_display = נטו מעוגל פחות נטו מעוגל, כך שהמספרים על המסך מסתדרים */}
        {!isCurrent && result.delta_display != null && <Delta value={result.delta_display} size="lg" />}
      </div>

      <p className="mt-4 whitespace-pre-line border-t border-border/70 pt-3 text-sm leading-relaxed text-ink-soft">
        {result.explanation}
      </p>

      {!isCurrent && !blocked && <BreakEven result={result} />}

      <OptionFacts result={result} isCurrent={isCurrent} />

      {complete && result.trace?.find((t) => t.key === "participation")?.source?.startsWith("קטלוג") && (
        <div className="mt-2 text-[11px] text-warn">ⓘ ההשתתפות כאן היא ברירת המחדל מהקטלוג — כדאי לוודא מול הנציג</div>
      )}

      {complete && <NetWaterfall steps={result.waterfall} total={result.delta_display} />}
      {result.trace?.length > 0 && (isCurrent || complete) && <Receipt current={isCurrent ? null : current} alt={result} defaultOpen={receiptOpen} />}
    </Card>
  );
}
