import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    tailwindcss(),
    // SPA mode: the app renders in the browser and builds to static files with a `_shell.html`
    // fallback. Turn SSR on per route later without changing the routes themselves.
    tanstackStart({ spa: { enabled: true } }),
    viteReact(),
  ],
  resolve: {
    tsconfigPaths: true,
  },
  // Same-origin in dev, so the backend needs no CORS. Start it with `bun dev:backend`.
  server: {
    proxy: {
      "/v1": "http://127.0.0.1:8000",
    },
  },
  // The SPA build prerenders `_shell.html` through a preview server. Left on `localhost` it binds
  // only ::1, and a Linux build host's fetch tries 127.0.0.1 and gets ECONNREFUSED.
  preview: {
    host: "127.0.0.1",
    proxy: {
      "/v1": "http://127.0.0.1:8000",
    },
  },
});
