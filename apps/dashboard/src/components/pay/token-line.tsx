import { PaymentMode } from "@/lib/receipts/payment-mode";
import { CopyButton } from "@stark/ui/components/copy-button";
import { formatToken } from "@stark/utils/format";

export function TokenLine({ token, note }: { token: string; note?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-row border border-line bg-canvas px-4 py-3">
      <span className="flex min-w-0 flex-[1_1_0] flex-col">
        <span className="tabular text-[15px] tracking-[0.02em] whitespace-nowrap sm:text-[17px] sm:tracking-[0.03em]">
          {formatToken(token)}
        </span>
        <span className="text-xs text-muted-foreground">
          {[note, PaymentMode.live ? null : "sample token"]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </span>
      <CopyButton value={token.replace(/\s+/g, "")} />
    </div>
  );
}
