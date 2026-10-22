import { Toggle } from "@stark/ui/components/toggle";
import { cn } from "@stark/ui/utils/cn";
import type { ComponentProps } from "react";

type ChoiceChipProps = Omit<ComponentProps<typeof Toggle>, "pressed" | "size"> & {
  selected: boolean;
  size?: "sm" | "lg";
};

/** A toggle in a group of quick picks (amounts, bill types). Never a slider. */
export function ChoiceChip({ selected, size = "lg", className, ...props }: ChoiceChipProps) {
  return (
    <Toggle
      pressed={selected}
      className={cn(
        "h-auto cursor-pointer border font-normal",
        size === "lg"
          ? "min-h-12 rounded-xl text-[15px]"
          : "min-h-9 rounded-full px-3.5 text-[13px]",
        "border-border text-foreground hover:border-white/16 hover:bg-card",
        size === "lg" ? "bg-card" : "bg-secondary",
        "aria-pressed:border-brand-warm/60 aria-pressed:bg-brand-tint aria-pressed:text-brand-soft",
        className,
      )}
      {...props}
    />
  );
}

export function ChipGroup({
  label,
  className,
  children,
  columns,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
  columns?: number;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(columns ? "grid gap-2" : "flex flex-wrap gap-2", className)}
      style={columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}
    >
      {children}
    </div>
  );
}
