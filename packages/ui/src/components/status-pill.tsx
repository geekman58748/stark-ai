import { Badge } from "@stark/ui/components/badge";
import { cn } from "@stark/ui/utils/cn";
import type { ReactNode } from "react";

/** A small status badge with a dot, e.g. "Running low". */
export function StatusPill({
  children,
  tone = "brand",
  className,
}: {
  children: ReactNode;
  tone?: "brand" | "muted";
  className?: string;
}) {
  return (
    <Badge
      variant="secondary"
      className={cn(
        "h-auto gap-1.5 bg-white/5 py-0.75 text-[11px] font-normal",
        tone === "brand" ? "text-brand-warm" : "text-muted-foreground",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-1.5 rounded-full", tone === "brand" ? "bg-brand-warm" : "bg-idle")}
      />
      {children}
    </Badge>
  );
}
