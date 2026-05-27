import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    {
      name: "deny-dockerfile-requests",
      configureServer(server) {
        server.middlewares.use((request, response, next) => {
          const pathname = request.url?.split("?", 1)[0];
          if (pathname === "/Dockerfile" || pathname.startsWith("/Dockerfile.")) {
            response.statusCode = 404;
            response.end("Not found");
            return;
          }
          next();
        });
      },
    },
    react(),
  ],
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
