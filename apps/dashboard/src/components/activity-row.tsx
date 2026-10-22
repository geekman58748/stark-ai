import type { Receipt } from "@stark/api";
import { cn } from "@stark/ui/cn";
import { listRowClass, RowText } from "@stark/ui/list-row";
import { formatActivityTime, formatNaira } from "@stark/utils/format";
import { Link } from "@tanstack/react-router";
import { receiptSubtitle, signedAmount, statusDisplay } from "@/lib/receipts";

export function ActivityRow({ receipt, selected }: { receipt: Receipt; selected?: boolean }) {
  const status = statusDisplay(receipt);
  return (
    <Link
      to="/activity"
      search={(prev) => ({ ...prev, receipt: receipt.id })}
      className={cn(
        listRowClass,
        "py-2.5 hover:text-fg",
        selected && "border-brand-warm/50 bg-surface-selected",
      )}
    >
      <span className="tabular w-11 text-xs text-muted">
        {formatActivityTime(receipt.created_at)}
      </span>
      <RowText
        title={<span className="font-normal">{receipt.bill_label}</span>}
        subtitle={receiptSubtitle(receipt)}
      />
      <span className={cn("text-sm", receipt.status === "declined" && "text-muted line-through")}>
        {formatNaira(signedAmount(receipt), { sign: receipt.type === "deposit" })}
      </span>
      <span
        className={cn(
          "min-w-[72px] text-right text-xs",
          status.tone === "brand" && "text-brand-warm",
          status.tone === "muted" && "text-muted",
          status.tone === "fg" && "text-fg",
        )}
      >
        {status.label}
      </span>
    </Link>
  );
}
