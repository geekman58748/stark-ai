import { cn } from "@stark/ui/utils/cn";
import { MethodIcon } from "@/components/auth/method-icon";
import type { Method } from "@/components/auth/methods";

export function MethodPickerOption({
  method,
  label,
  active,
  onSelect,
}: {
  method: Method;
  label: string;
  active: boolean;
  onSelect: (method: Method) => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => onSelect(method)}
      className={cn(
        "flex h-11 cursor-pointer items-center justify-center gap-2 rounded-xl border px-3 text-[13px] font-medium transition-colors",
        "focus-visible:border-brand focus-visible:ring-3 focus-visible:ring-brand/25 focus-visible:outline-none",
        active
          ? "border-brand/60 bg-brand-wash text-fg"
          : "border-line-2 bg-white/2 text-fg-2 hover:border-white/20 hover:text-fg",
      )}
    >
      <MethodIcon method={method} />
      {label}
    </button>
  );
}
