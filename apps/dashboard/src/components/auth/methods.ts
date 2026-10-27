export const AUTH_CARD = "#15171b";

export const METHODS = [
  { id: "email", label: "Email" },
  { id: "google", label: "Google" },
  { id: "phone", label: "Phone" },
  { id: "telegram", label: "Telegram" },
] as const;

export type Method = (typeof METHODS)[number]["id"];
