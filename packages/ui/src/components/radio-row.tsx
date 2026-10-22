import type { ReactNode } from "react";
import { cn } from "../utils/cn";

/** One option in a list of choices, with a round indicator on the right. */
export function RadioRow({
  checked,
  onSelect,
  title,
  subtitle,
  disabled,
}: {
  checked: boolean;
  onSelect: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        "flex min-h-[60px] w-full cursor-pointer items-center gap-3 rounded-row border px-4 py-2.5 text-left text-sm text-fg transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "border-brand-warm/60 bg-surface-selected" : "border-white/8 bg-surface",
      )}
    >
      <span className="flex flex-1 flex-col">
        <span className="font-medium">{title}</span>
        {subtitle ? <span className="text-xs text-muted">{subtitle}</span> : null}
      </span>
      <span
        aria-hidden="true"
        className={cn(
          "box-border size-[18px] flex-none rounded-full",
          checked ? "border-[5px] border-brand-warm" : "border-2 border-faint",
        )}
      />
    </button>
  );
}

export function RadioList({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-col gap-2">
      {children}
    </div>
  );
}
