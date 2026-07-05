import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev-server proxy: the console runs on :5173 and forwards API paths to uvicorn.
// In production the same paths are routed by Caddy, so the app always calls
// same-origin URLs and needs no CORS.
const API_PREFIXES = [
  "/auth",
  "/users",
  "/health",
  "/workflow",
  "/governance",
  "/evals",
  "/environment",
  "/resilience",
];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      API_PREFIXES.map((prefix) => [prefix, "http://localhost:8000"]),
    ),
  },
});
