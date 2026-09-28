import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_PROXY_TARGET =
  process.env.VITE_API_BASE_URL || process.env.ROLLER_API_URL || "http://127.0.0.1:8791";

export default defineConfig({
  plugins: [react()],
  publicDir: "../roller-terminal/public",
  server: {
    port: 5180,
    strictPort: true,
    host: "127.0.0.1",
    fs: {
      allow: [".."],
    },
    proxy: {
      "/api": {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
