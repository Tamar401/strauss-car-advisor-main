import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// בפיתוח: כל קריאה ל-/api עוברת לשרת ה-FastAPI
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
});
