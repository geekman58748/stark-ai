import type { Bill } from "@stark/api";

export type BillSection = keyof typeof BillSections.all;

export class BillSections {
  static readonly all = {
    all: { label: "All", kinds: null },
    electricity: { label: "Electricity", kinds: ["electricity"] },
    phone: { label: "Airtime and data", kinds: ["airtime", "data"] },
    home: { label: "TV and internet", kinds: ["tv", "internet", "water"] },
  } as const;

  static tabs(): { value: BillSection; label: string }[] {
    return Object.entries(BillSections.all).map(([value, s]) => ({
      value: value as BillSection,
      label: s.label,
    }));
  }

  static filter(bills: Bill[], section: BillSection): Bill[] {
    const kinds = BillSections.all[section].kinds as readonly string[] | null;
    return bills.filter((b) => !kinds || kinds.includes(b.kind));
  }
}
