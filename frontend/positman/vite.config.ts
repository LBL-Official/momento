import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_PROXY_TARGET = process.env.VITE_API_BASE_URL || "http://127.0.0.1:8791";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5194,
    strictPort: true,
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
