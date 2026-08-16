import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend default port (override with REPRO_BACKEND_PORT if needed)
const backend = process.env.REPRO_BACKEND_PORT || 8000;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${backend}`,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
