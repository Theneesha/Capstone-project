import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend, so the browser never makes a cross-origin
// request (no CORS / "Failed to fetch" problems). Change the target if your backend uses another port.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } } },
});
