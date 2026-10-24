import type { DueBill } from "@stark/api";
import { formatNaira } from "@stark/utils/format";

/**
 * Renewal copy for the screens. `state.due_soon` is already sorted by the server
 * (soonest first, overdue included), so the UI never re-sorts or filters — it
 * renders what the reminder engine decided is worth saying.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** `YYYY-MM-DD` as a local date. `new Date("2026-10-27")` is UTC midnight, which
 *  renders as the day before for anyone west of Greenwich. */
export function renewalDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

/** `Oct 27` — the day itself, not the time of day. */
export function renewalDay(iso: string): string | null {
  const date = renewalDate(iso);
  return date ? `${MONTHS[date.getMonth()]} ${date.getDate()}` : null;
}

/** "today", "tomorrow", "in 3 days", "2 days ago" — the same grammar the server speaks. */
export function renewalWhen(daysUntil: number): string {
  if (daysUntil === 0) return "today";
  if (daysUntil === 1) return "tomorrow";
  if (daysUntil > 1) return `in ${daysUntil} days`;
  return `${-daysUntil} day${daysUntil === -1 ? "" : "s"} ago`;
}

/** The soonest renewal, or null when nothing is in the window. */
export function nextRenewal(due: DueBill[] | undefined): DueBill | null {
  return due?.[0] ?? null;
}

/** "Living room TV renews in 3 days" — the label the user gave the bill. */
export function renewalTitle(due: DueBill): string {
  return due.days_until < 0
    ? `${due.label} was due ${renewalWhen(due.days_until)}`
    : `${due.label} renews ${renewalWhen(due.days_until)}`;
}

/** "DStv · ₦7,900 · 27 Oct" — the facts behind the sentence, price optional. */
export function renewalDetail(due: DueBill): string {
  const parts = [due.provider];
  if (due.price_ngn) parts.push(formatNaira(due.price_ngn));
  const day = renewalDay(due.renews_on);
  if (day) parts.push(day);
  return parts.join(" · ");
}
