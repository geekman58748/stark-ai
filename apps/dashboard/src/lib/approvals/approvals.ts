import type { ApprovalWindow, PaymentRequest } from "@stark/api/types";

export class Approvals {
  static readonly WINDOWS: { value: ApprovalWindow; label: string }[] = [
    { value: 15, label: "15 min" },
    { value: 30, label: "30 min" },
    { value: 60, label: "1 hour" },
    { value: 360, label: "6 hours" },
    { value: 1440, label: "1 day" },
  ];

  static waiting(requests: PaymentRequest[], now = Date.now()): PaymentRequest[] {
    return requests.filter((r) => r.status === "pending" && Date.parse(r.expires_at) > now);
  }

  static reason(request: PaymentRequest): string {
    return request.reason === "over_cap"
      ? "Over your monthly limit"
      : "Over your limit for one payment";
  }

  static timeLeft(request: PaymentRequest, now = Date.now()): string {
    const minutes = Math.max(Math.ceil((Date.parse(request.expires_at) - now) / 60_000), 0);
    if (minutes < 60) return `${minutes} min left to decide`;
    const hours = Math.floor(minutes / 60);
    return `${hours} h ${minutes % 60} min left to decide`;
  }

  static outcome(request: PaymentRequest): string {
    switch (request.status) {
      case "pending":
        return "Waiting on you";
      case "approved":
        return "You approved it";
      case "denied":
        return "You declined it";
      case "expired":
        return "Expired, nothing paid";
    }
  }
}
