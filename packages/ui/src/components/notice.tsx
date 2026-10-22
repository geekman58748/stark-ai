import { cn } from "@stark/ui/utils/cn";
import type { ReactNode } from "react";

/** A highlighted strip for something that needs the user (low meter, a refused payment). */
export function Notice({
  icon,
  title,
  children,
  actions,
  tone = "brand",
  className,
}: {
  icon?: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: "brand" | "muted";
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-card border p-4",
        tone === "brand" ? "border-brand-warm/40 bg-brand-wash" : "border-line bg-surface",
        className,
      )}
    >
      {icon}
      <span className="flex flex-[1_1_240px] flex-col">
        <span className="font-medium">{title}</span>
        {children ? <span className="text-[13px] text-fg-2">{children}</span> : null}
      </span>
      {actions}
    </section>
  );
}
