import type { Bill, BillKind, State } from "@stark/api";
import type { IconName } from "@stark/ui/components/icons";
import { formatNaira, formatShortDate, maskReference } from "@stark/utils/format";

export const billKinds: { kind: BillKind; label: string; icon: IconName }[] = [
  { kind: "electricity", label: "Electricity", icon: "Electricity" },
  { kind: "airtime", label: "Airtime", icon: "Airtime" },
  { kind: "data", label: "Data", icon: "Data" },
  { kind: "tv", label: "Cable TV", icon: "Tv" },
  { kind: "internet", label: "Internet", icon: "Internet" },
  { kind: "water", label: "Water", icon: "Water" },
];

export function kindLabel(kind: BillKind) {
  return billKinds.find((k) => k.kind === kind)?.label ?? kind;
}

export function kindIcon(kind: BillKind): IconName {
  return billKinds.find((k) => k.kind === kind)?.icon ?? "Bills";
}

/** Below this many days we flag the meter as running low. */
export const LOW_DAYS = 5;

/** `units_left`/`days_left` describe the user's electricity, so only the first meter gets them. */
export function meterBill(state: State) {
  return state.bills.find((b) => b.kind === "electricity");
}

export function billSubtitle(bill: Bill) {
  const parts = [kindLabel(bill.kind), bill.provider];
  if (bill.kind === "electricity") parts.push(`meter ${maskReference(bill.reference)}`);
  if (bill.kind === "airtime" || bill.kind === "data") parts.push(maskReference(bill.reference));
  return parts.join(" · ");
}

export type BillStatus = { text: string; attention: boolean };

export function billStatus(bill: Bill, state: State): BillStatus {
  if (bill.kind === "electricity" && meterBill(state)?.id === bill.id && state.days_left !== null) {
    return {
      text: `About ${state.days_left} day${state.days_left === 1 ? "" : "s"} left`,
      attention: state.days_left <= LOW_DAYS,
    };
  }
  if (bill.kind === "internet" || bill.kind === "water") {
    return { text: "Saved, paying soon", attention: false };
  }
  if (bill.plan_price_ngn) {
    return {
      text: bill.last_paid_at
        ? `${formatNaira(bill.plan_price_ngn)} plan · paid ${formatShortDate(bill.last_paid_at)}`
        : `${formatNaira(bill.plan_price_ngn)} plan`,
      attention: false,
    };
  }
  if (bill.last_paid_at) {
    return { text: `Last paid ${formatShortDate(bill.last_paid_at)}`, attention: false };
  }
  return { text: "Not paid yet", attention: false };
}

/** Internet and water can be saved but not paid yet (the backend refuses and charges nothing). */
export function isPayable(bill: Bill) {
  return bill.kind !== "internet" && bill.kind !== "water";
}

/** Data and TV are sold as fixed plans: the amount is the plan price, never typed. */
export function fixedAmount(bill: Bill) {
  return bill.plan_price_ngn ?? null;
}

export const referenceLabel: Record<BillKind, string> = {
  electricity: "Meter number",
  airtime: "Phone number",
  data: "Phone number",
  tv: "Smartcard number",
  internet: "Account number",
  water: "Account number",
};

export const providers: Record<BillKind, string[]> = {
  // Only Ikeja Electric is confirmed with the vendor today.
  electricity: ["Ikeja Electric"],
  airtime: ["MTN", "Airtel", "Glo", "9mobile"],
  data: ["MTN", "Airtel", "Glo", "9mobile"],
  tv: ["DStv", "GOtv", "Startimes", "Showmax"],
  internet: ["Spectranet", "Smile", "Other"],
  water: ["Lagos Water Corporation", "Other"],
};

export const defaultNickname: Record<BillKind, string> = {
  electricity: "Home",
  airtime: "My line",
  data: "My data",
  tv: "Living room TV",
  internet: "Wi-Fi",
  water: "Water",
};
