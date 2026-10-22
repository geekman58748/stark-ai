import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), reactRouter()],
  resolve: {
    tsconfigPaths: true,
  },
  // Same-origin in dev, so the backend needs no CORS. Start it with `pnpm backend`.
  server: {
    proxy: {
      "/v1": "http://127.0.0.1:8000",
    },
  },
});
