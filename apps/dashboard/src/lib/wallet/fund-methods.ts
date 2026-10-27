export type FundMethod = (typeof FundMethods.all)[number]["id"];

export class FundMethods {
  static readonly all = [
    {
      id: "bank",
      name: "Bank transfer",
      note: "Recommended · lands in minutes",
      source: "Bank transfer",
      detail: "You’ll get your own account number to send to.",
    },
    {
      id: "card",
      name: "Debit card",
      note: "Visa, Mastercard, Verve",
      source: "Debit card",
      detail: "You’ll confirm the payment in your bank app.",
    },
    {
      id: "crypto",
      name: "I already have crypto",
      note: "Send almost any coin",
      source: "Crypto deposit",
      detail: "Whatever you send is changed into naira in your Stark balance.",
    },
  ] as const;

  static get(id: FundMethod) {
    return FundMethods.all.find((m) => m.id === id)!;
  }
}
