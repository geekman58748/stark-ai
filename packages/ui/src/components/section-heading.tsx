import { Eyebrow } from "@stark/ui/components/eyebrow";
import { cn } from "@stark/ui/utils/cn";
import type { ReactNode } from "react";

/** Eyebrow, a hairline rule, and an optional trailing action or count. */
export function SectionHeading({
  children,
  action,
  className,
}: {
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mt-2 flex items-center gap-3", className)}>
      <Eyebrow>{children}</Eyebrow>
      <span aria-hidden="true" className="h-px flex-1 bg-white/8" />
      {action ? <span className="text-xs text-muted-foreground">{action}</span> : null}
    </div>
  );
}
