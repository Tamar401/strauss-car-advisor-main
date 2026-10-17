// עיגול לשקל רק כאן — בתצוגה. החישוב בשרת ללא עיגול.
const shekel = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 });

export const fmt = (n) => (n == null ? "—" : `${shekel.format(Math.round(n))} ₪`);

export const fmtDelta = (n) => {
  if (n == null) return "—";
  const r = Math.round(n);
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${shekel.format(Math.abs(r))} ₪`;
};
