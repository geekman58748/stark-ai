import { cn } from "@stark/ui/utils/cn";
import type { CSSProperties, ReactNode } from "react";

/** A transcript line that fades in after `delay`. */
export function VoiceLine({
  delay,
  className,
  children,
}: {
  delay: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={cn("voice-in", className)} style={{ "--d": delay } as CSSProperties}>
      {children}
    </span>
  );
}
