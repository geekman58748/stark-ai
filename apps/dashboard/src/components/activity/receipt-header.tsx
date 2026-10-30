import { Eyebrow } from "@stark/ui/components/eyebrow";
import { StatusPill } from "@stark/ui/components/status-pill";
import type { StatusDisplay } from "@/lib/receipts/receipts";

export function ReceiptHeader({ status }: { status: StatusDisplay }) {
  return (
    <div className="flex items-center gap-2">
      <Eyebrow>Receipt</Eyebrow>
      <StatusPill tone={status.tone === "brand" ? "brand" : "muted"} className="ml-auto">
        {status.label}
      </StatusPill>
    </div>
  );
}
