import type { Receipt } from "@stark/api";

export type StatusDisplay = { label: string; tone: "brand" | "muted" | "fg" };

/** A payment is only done when it is `delivered`. Everything else says plainly what happened. */
export function statusDisplay(r: Receipt): StatusDisplay {
  switch (r.status) {
    case "delivered":
      return { label: "Paid", tone: "brand" };
    case "pending":
      return { label: "Going through", tone: "fg" };
    case "failed":
      return { label: "Didn’t go through", tone: "muted" };
    case "declined":
      return { label: "Declined", tone: "muted" };
    case "received":
      return { label: "Received", tone: "muted" };
    case "sent":
      return { label: "Sent", tone: "muted" };
  }
}

export function receiptSubtitle(r: Receipt) {
  if (r.status === "declined") return "Stark stopped this. Nothing was charged.";
  if (r.status === "failed") return "Nothing was charged";
  if (r.status === "pending") return "Still going through. Not paid yet.";
  if (r.type === "withdrawal") return r.source ?? "To your bank";
  return r.source ?? "";
}

export function signedAmount(r: Receipt) {
  if (r.type === "deposit") return r.amount_ngn;
  if (r.type === "withdrawal") return -r.amount_ngn;
  return r.amount_ngn;
}

export type ActivityFilter = "all" | "bills" | "in" | "declined";

export function matchesFilter(r: Receipt, filter: ActivityFilter) {
  switch (filter) {
    case "all":
      return true;
    case "bills":
      return (r.type === "bill" || r.type === "autotopup") && r.status === "delivered";
    case "in":
      return r.type === "deposit";
    case "declined":
      return r.status === "declined" || r.status === "failed";
  }
}

/** Payments are dry-run until the vendor is live, so tokens are labelled as samples. */
export const livePayments = import.meta.env.VITE_STARK_LIVE_PAYMENTS === "true";
