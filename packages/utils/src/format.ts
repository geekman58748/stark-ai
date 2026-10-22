const naira = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });

/** Money is integer naira everywhere. `5000` renders as `₦5,000`. */
export function formatNaira(amount: number, opts: { sign?: boolean } = {}): string {
  const body = `₦${naira.format(Math.abs(amount))}`;
  if (amount < 0) return `−${body}`;
  return opts.sign && amount > 0 ? `+${body}` : body;
}

/** Plain digits for an amount field: `30000` → `30,000`. */
export function formatAmountInput(amount: number): string {
  return amount ? naira.format(amount) : "";
}

/** Reads a typed amount back to integer naira, ignoring commas and the naira sign. */
export function parseAmountInput(value: string): number {
  return Number(value.replace(/[^0-9]/g, "")) || 0;
}

/** Hides all but the last four characters of a meter, phone or smartcard number. */
export function maskReference(reference: string): string {
  const tail = reference.replace(/\s+/g, "").slice(-4);
  return `•••• ${tail}`;
}

/** Groups a 20-digit meter token into blocks of four. */
export function formatToken(token: string): string {
  return token
    .replace(/\s+/g, "")
    .replace(/(.{4})/g, "$1 ")
    .trim();
}

const shortDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
const longDate = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});
const clock = new Intl.DateTimeFormat("en-NG", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const clock12 = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });

function isSameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

/** `Oct 14` */
export function formatShortDate(iso: string): string {
  return shortDate.format(new Date(iso));
}

/** `Oct 20, 2026` */
export function formatLongDate(iso: string): string {
  return longDate.format(new Date(iso));
}

/** `Oct 14, 9:41 PM` */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return `${shortDate.format(d)}, ${clock12.format(d)}`;
}

/** Time of day for today's rows (`21:41`), the date for anything older (`Oct 12`). */
export function formatActivityTime(iso: string, now = new Date()): string {
  const d = new Date(iso);
  return isSameDay(d, now) ? clock.format(d) : shortDate.format(d);
}

export function isToday(iso: string, now = new Date()): boolean {
  return isSameDay(new Date(iso), now);
}

export function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
