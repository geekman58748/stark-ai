import { cn } from "@stark/ui/utils/cn";
import type { HTMLAttributes } from "react";

/** Small uppercase label above a number or a group. */
export function Eyebrow({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "tabular text-[11px] tracking-[0.08em] text-muted-foreground uppercase",
        className,
      )}
      {...props}
    />
  );
}
