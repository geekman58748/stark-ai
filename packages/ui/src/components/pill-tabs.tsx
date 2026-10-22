import type { ReactNode } from "react";
import { cn } from "../utils/cn";

export type PillTab<T extends string> = { value: T; label: ReactNode };

/** Section filter pills (All / Electricity / ...). Controlled; renders buttons. */
export function PillTabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  className,
}: {
  tabs: PillTab<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <div role="tablist" aria-label={label} className={cn("flex flex-wrap gap-2", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={tab.value === value}
          onClick={() => onChange(tab.value)}
          className={pillTabClass(tab.value === value)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function pillTabClass(active: boolean) {
  return cn(
    "inline-flex min-h-[34px] cursor-pointer items-center rounded-full border px-3.5 text-[13px] no-underline",
    active
      ? "border-brand-line bg-brand-tint text-brand-soft"
      : "border-transparent bg-surface-2 text-fg hover:border-white/10",
  );
}
