import type { StatusDisplay } from "@/lib/receipts/receipts";
import { cn } from "@stark/ui/utils/cn";

export function ActivityRowStatus({ status }: { status: StatusDisplay }) {
  return (
    <span
      className={cn(
        "min-w-18 text-right text-xs",
        status.tone === "brand" && "text-brand-warm",
        status.tone === "muted" && "text-muted-foreground",
        status.tone === "fg" && "text-fg",
      )}
    >
      {status.label}
    </span>
  );
}
