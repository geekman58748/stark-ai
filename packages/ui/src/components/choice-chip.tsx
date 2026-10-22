import type { ButtonHTMLAttributes } from "react";
import { cn } from "../utils/cn";

type ChoiceChipProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  selected: boolean;
  size?: "sm" | "lg";
};

/** A toggle in a group of quick picks (amounts, bill types). Never a slider. */
export function ChoiceChip({ selected, size = "lg", className, ...props }: ChoiceChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "cursor-pointer border font-[inherit] transition-colors",
        size === "lg"
          ? "min-h-12 rounded-xl text-[15px]"
          : "min-h-9 rounded-full px-3.5 text-[13px]",
        selected
          ? "border-brand-warm/60 bg-brand-tint text-brand-soft"
          : cn(
              "border-white/8 text-fg hover:border-white/16",
              size === "lg" ? "bg-surface" : "bg-surface-2",
            ),
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
