import { cn } from "../utils/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("block animate-pulse rounded-lg bg-white/6", className)}
    />
  );
}
