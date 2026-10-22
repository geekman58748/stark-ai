/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where "Get started" and "Log in" go. Defaults to the local dashboard. */
  readonly VITE_DASHBOARD_URL?: string;
  /** The Telegram bot's t.me link, once it is public. */
  readonly VITE_TELEGRAM_BOT_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
