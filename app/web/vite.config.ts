import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The production build is served by FastAPI from app/web/dist (one process). During development,
// `npm run dev` proxies /api to the FastAPI server on port 8000.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
