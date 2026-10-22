import type { ReactNode } from "react";
import { cn } from "../utils/cn";

export function SwitchRow({
  checked,
  onChange,
  title,
  subtitle,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: ReactNode;
  subtitle?: ReactNode;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex w-full cursor-pointer items-center gap-3 rounded-row border border-line bg-surface px-4 py-3 text-left text-fg"
    >
      <span className="flex flex-1 flex-col">
        <span className="font-medium">{title}</span>
        {subtitle ? <span className="text-xs text-muted">{subtitle}</span> : null}
      </span>
      <span
        aria-hidden="true"
        className={cn(
          "relative h-6 w-10 flex-none rounded-full transition-colors",
          checked ? "bg-brand" : "bg-track",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 size-5 rounded-full bg-white transition-[left]",
            checked ? "left-[18px]" : "left-0.5",
          )}
        />
      </span>
    </button>
  );
}
