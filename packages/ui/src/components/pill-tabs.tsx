import { Tabs, TabsList, TabsTrigger } from "@stark/ui/components/tabs";
import { cn } from "@stark/ui/utils/cn";
import type { ReactNode } from "react";

export type PillTab<T extends string> = { value: T; label: ReactNode };

/** Section filter pills (All / Electricity / ...): shadcn Tabs styled as Stark pills. */
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
    <Tabs value={value} onValueChange={(v) => onChange(v as T)}>
      <TabsList
        aria-label={label}
        className={cn("h-auto flex-wrap justify-start gap-2 bg-transparent p-0", className)}
      >
        {tabs.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className={cn(pillTabClass(tab.value === value), "h-auto flex-none shadow-none")}
          >
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

/** The pill look on its own, for links that act as section tabs. */
export function pillTabClass(active: boolean) {
  return cn(
    "inline-flex min-h-[34px] cursor-pointer items-center rounded-full border px-3.5 text-[13px] font-normal no-underline",
    active
      ? "border-brand-line bg-brand-tint text-brand-soft dark:text-brand-soft dark:data-active:bg-brand-tint dark:data-active:border-brand-line dark:data-active:text-brand-soft"
      : "border-transparent bg-secondary text-foreground hover:border-white/10 dark:text-foreground",
  );
}
