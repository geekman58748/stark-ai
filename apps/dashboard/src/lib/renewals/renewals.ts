import type { DueBill } from "@stark/api";
import { formatNaira } from "@stark/utils/format";

export class Renewals {
  private static readonly MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  static date(iso: string): Date | null {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!match) return null;
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }

  static day(iso: string): string | null {
    const date = Renewals.date(iso);
    return date
      ? `${Renewals.MONTHS[date.getMonth()]} ${date.getDate()}`
      : null;
  }

  static when(daysUntil: number): string {
    if (daysUntil === 0) return "today";
    if (daysUntil === 1) return "tomorrow";
    if (daysUntil > 1) return `in ${daysUntil} days`;
    return `${-daysUntil} day${daysUntil === -1 ? "" : "s"} ago`;
  }

  static next(due: DueBill[] | undefined): DueBill | null {
    return due?.[0] ?? null;
  }

  static title(due: DueBill): string {
    return due.days_until < 0
      ? `${due.label} was due ${Renewals.when(due.days_until)}`
      : `${due.label} renews ${Renewals.when(due.days_until)}`;
  }

  static detail(due: DueBill): string {
    const parts = [due.provider];
    if (due.price_ngn) parts.push(formatNaira(due.price_ngn));
    const day = Renewals.day(due.renews_on);
    if (day) parts.push(day);
    return parts.join(" · ");
  }
}
