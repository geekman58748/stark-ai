import type { ReactNode } from "react";
import { cn } from "../utils/cn";

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
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2 py-[3px] text-[11px]",
        tone === "brand" ? "text-brand-warm" : "text-muted",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-1.5 rounded-full", tone === "brand" ? "bg-brand-warm" : "bg-muted")}
      />
      {children}
    </span>
  );
}
