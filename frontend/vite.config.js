import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// For Codespaces/local (no Docker): default proxy -> localhost:8000
// For Docker Compose: set VITE_PROXY_TARGET=http://backend:8000
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target,
        changeOrigin: true
      }
    }
  }
});
