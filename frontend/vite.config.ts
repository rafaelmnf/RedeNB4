import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento (npm run dev) o Vite repassa /api e /ws para o backend.
// Em uso normal, o build (dist/) é servido pelo próprio FastAPI na porta 8000.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1500 },
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace("http", "ws"), ws: true },
    },
  },
});
