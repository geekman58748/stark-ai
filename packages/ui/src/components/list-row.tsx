import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../utils/cn";

export const listRowClass =
  "flex flex-wrap items-center gap-3 rounded-row border border-line bg-surface px-4 py-3 text-fg no-underline transition-colors hover:border-white/12";

/** A row's title and grey subtitle. Grows to fill the row. */
export function RowText({
  title,
  subtitle,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("flex min-w-0 flex-[1_1_0] flex-col sm:flex-[1_1_180px]", className)}>
      <span className="truncate font-medium">{title}</span>
      {subtitle ? <span className="text-xs text-muted">{subtitle}</span> : null}
    </span>
  );
}

export function ListRow({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(listRowClass, className)} {...props} />;
}

export function RowList({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-2", className)} {...props} />;
}
