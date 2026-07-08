/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The frontend is served independently of Flask. In dev, /api is proxied to
// Flask so the browser sees a single origin (no CORS). `npm run build` emits
// to the default dist/, served by any static host (or `npm run preview`).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:5000",
    },
  },
  test: {
    globals: true,
    environment: "node",
  },
});
