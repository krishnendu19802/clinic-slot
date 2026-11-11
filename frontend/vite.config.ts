import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The dev server proxies /api to Django so the httpOnly refresh cookie stays same-origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "node" },
});
