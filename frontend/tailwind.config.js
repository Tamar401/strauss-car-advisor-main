/** צבעים מוגדרים כ-CSS variables ב-src/design/tokens.css — כאן רק ממפים אותם לשמות של Tailwind */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

const PETALS = ["red", "orange", "yellow", "lime", "green", "teal", "blue"];

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  // דוגמאות הצבע בעמוד /design וצבעי ההנעה בכרטיסים בנויים דינמית
  safelist: [
    { pattern: /^bg-(brand|accent|up|down|warn|ink|ink-soft|muted|surface|border)$/ },
    { pattern: /^(bg|text|border)-petal-(red|orange|yellow|lime|green|teal|blue)(\/10|\/15)?$/ },
  ],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        surface: v("surface"),
        muted: v("muted"),
        border: v("border"),
        ink: v("ink"),
        "ink-soft": v("ink-soft"),
        brand: v("brand"),
        "brand-soft": v("brand-soft"),
        accent: v("accent"),
        up: v("up"),
        "up-soft": v("up-soft"),
        down: v("down"),
        "down-soft": v("down-soft"),
        warn: v("warn"),
        "warn-soft": v("warn-soft"),
        petal: Object.fromEntries(PETALS.map((p) => [p, v(`petal-${p}`)])),
      },
      fontFamily: {
        sans: ["Heebo", "system-ui", "sans-serif"],
        display: ["Rubik", "Heebo", "sans-serif"],
      },
      borderRadius: { xl: "14px", "2xl": "20px", "3xl": "28px" },
      boxShadow: {
        card: "0 1px 2px rgb(60 20 20 / .04), 0 8px 28px -6px rgb(60 20 20 / .10)",
        lift: "0 2px 4px rgb(60 20 20 / .05), 0 18px 40px -8px rgb(60 20 20 / .18)",
        glow: "0 8px 24px -6px rgb(var(--brand) / .45)",
      },
    },
  },
  plugins: [],
};
