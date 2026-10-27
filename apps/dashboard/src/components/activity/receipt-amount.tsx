import { Receipts } from "@/lib/receipts/receipts";
import type { Receipt } from "@stark/api";
import { cn } from "@stark/ui/utils/cn";
import { formatDateTime, formatNaira } from "@stark/utils/format";

export function ReceiptAmount({ receipt }: { receipt: Receipt }) {
  return (
    <div className="flex flex-col gap-1">
      <span
        className={cn(
          "font-serif text-5xl leading-none",
          receipt.status === "declined" && "text-muted-foreground",
        )}
      >
        {formatNaira(Receipts.signedAmount(receipt), {
          sign: receipt.type === "deposit",
        })}
      </span>
      <span className="text-xs text-muted-foreground">
        {receipt.bill_label} · {formatDateTime(receipt.created_at)}
      </span>
    </div>
  );
}
