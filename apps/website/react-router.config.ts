import type { Config } from "@react-router/dev/config";

// Static hosting: every route is rendered to HTML at build time, no server at runtime.
export default {
  ssr: false,
  prerender: true,
} satisfies Config;
