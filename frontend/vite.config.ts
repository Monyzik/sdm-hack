import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5180,
    strictPort: true,
    allowedHosts: ["sdmhack.miposts.ru"],
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
      "/agents": {
        target: "http://agents:8010",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agents/, ""),
      },
    },
  },
});
