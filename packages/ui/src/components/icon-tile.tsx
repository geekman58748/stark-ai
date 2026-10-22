import { cn } from "@stark/ui/utils/cn";
import type { ReactNode } from "react";

/** The rounded orange-tinted square that holds a bill or method icon. */
export function IconTile({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-9 flex-none items-center justify-center rounded-[10px] bg-brand/20 text-brand-warm",
        className,
      )}
    >
      {children}
    </span>
  );
}
