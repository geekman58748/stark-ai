import type { Receipt } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { ReceiptAmount } from "@/components/activity/receipt-amount";
import { ReceiptHeader } from "@/components/activity/receipt-header";
import { ReceiptNote } from "@/components/activity/receipt-note";
import { ReceiptStats } from "@/components/activity/receipt-stats";
import { TokenLine } from "@/components/pay/token-line";
import { Receipts } from "@/lib/receipts/receipts";

export function ReceiptCard({ receipt }: { receipt: Receipt }) {
  return (
    <Card aria-live="polite">
      <ReceiptHeader status={Receipts.status(receipt)} />
      <ReceiptAmount receipt={receipt} />
      <ReceiptNote status={receipt.status} />
      {receipt.token && receipt.status === "delivered" ? <TokenLine token={receipt.token} /> : null}
      <ReceiptStats receipt={receipt} />
    </Card>
  );
}
