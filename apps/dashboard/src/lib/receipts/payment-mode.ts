export class PaymentMode {
  static readonly live = import.meta.env.VITE_STARK_LIVE_PAYMENTS === "true";
}
