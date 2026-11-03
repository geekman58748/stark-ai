const dashboard = (import.meta.env.VITE_DASHBOARD_URL ?? "http://localhost:5174").replace(
  /\/$/,
  "",
);

export const links = {
  getStarted: `${dashboard}/start`,
  logIn: dashboard,
  talk: `${dashboard}/talk`,
  demo: `${dashboard}/demo`,
  telegram: import.meta.env.VITE_TELEGRAM_BOT_URL ?? `${dashboard}/start`,
};
