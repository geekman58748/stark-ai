import type { FundMethod } from "@/lib/wallet/fund-methods";
import type { IconName } from "@stark/ui/components/icons";

export type FundingWay = {
  method: FundMethod;
  title: string;
  subtitle: string;
  icon: IconName;
};

export class FundingWays {
  static readonly all: FundingWay[] = [
    {
      method: "bank",
      title: "Bank transfer",
      subtitle: "Your own account number",
      icon: "Bank",
    },
    {
      method: "card",
      title: "Debit card",
      subtitle: "Visa, Mastercard, Verve",
      icon: "Card",
    },
    {
      method: "crypto",
      title: "Crypto",
      subtitle: "Send almost any coin",
      icon: "Coins",
    },
  ];
}
