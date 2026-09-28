import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Fallback proxy only. Browser calls use API_BASE_URL → :8791 in development. */
const API_PROXY_TARGET =
  process.env.VITE_API_BASE_URL || process.env.ROLLER_API_URL || "http://127.0.0.1:8791";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5179,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
