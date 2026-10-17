// "דף העובדות" של חלופה — בדיוק הרשימה שההנחיות דורשות לכל חלופה:
// זכאות ולמה, עלות ותקציב, השתתפויות, שווי שימוש, החזר חשמל או אחזקה. בעלות: מפתחת א'.
import { Money } from "../design/components";

function Fact({ label, children, wide = false }) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <dt className="text-[11px] text-ink-soft">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{children}</dd>
    </div>
  );
}

export default function OptionFacts({ result, isCurrent }) {
  const e = result.eligibility;
  const waiver = result.option.kind === "waiver";
  const known = result.status !== "blocked";

  return (
    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 rounded-2xl bg-muted/50 p-3">
      {!isCurrent && (
        <Fact label="זכאות" wide>
          <span className={e.eligible ? "text-up" : "text-down"}>{e.eligible ? "✓ זכאי/ת" : "✕ לא זכאי/ת"}</span>
          <span className="font-normal text-ink-soft"> — {e.reason_text}</span>
        </Fact>
      )}

      {/* שני שדות נפרדים ולא "עלות / תקציב" — בכיוון RTL הצמד מתהפך ומבלבל */}
      {!waiver && result.monthly_cost != null && (
        <>
          <Fact label="עלות חודשית לחברה">
            <Money value={result.monthly_cost} />
          </Fact>
          <Fact label="תקציב הקבוצה שלך">
            <Money value={result.budget} />
          </Fact>
        </>
      )}
      {waiver && (
        <Fact label="תקציב הקבוצה">
          <Money value={result.budget} />
          <div className="text-[11px] font-normal text-ink-soft">תקציב שלא נוצל לא הופך לשכר</div>
        </Fact>
      )}

      {known && !waiver && (
        <Fact label="השתתפות שלך">
          {result.employee_participation != null ? <Money value={result.employee_participation} /> : <span className="text-warn">ממתין לנציג</span>}
        </Fact>
      )}

      {result.family_gap_employee > 0 && (
        <Fact label="חלקך בפער (מסלול משפחתי)">
          <Money value={result.family_gap_employee} />
        </Fact>
      )}

      {!waiver && (
        <Fact label="שווי שימוש (לא משולם, חייב במס)">
          <Money value={result.value_of_use} />
        </Fact>
      )}

      {waiver ? (
        <Fact label="אחזקת רכב (חייבת במס)">
          <Money value={result.maintenance} />
        </Fact>
      ) : (
        result.drive === "electric" &&
        known && (
          <Fact label="החזר חשמל">
            {result.electric_bonus_gross ? (
              // הסכום נטו מגיע מקובץ הכללים ומופיע בהסבר; כאן — מה שהמנוע חישב בפועל
              <>
                <Money value={result.electric_bonus_gross} /> <span className="text-[11px] font-normal text-ink-soft">ברוטו</span>
              </>
            ) : (
              <span className="text-ink-soft">יחושב כשיהיו כל הנתונים</span>
            )}
          </Fact>
        )
      )}
    </dl>
  );
}
