import type { HTMLAttributes } from "react";
import { cn } from "../utils/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        "flex flex-col gap-3.5 rounded-card border border-line bg-surface p-5",
        className,
      )}
      {...props}
    />
  );
}
