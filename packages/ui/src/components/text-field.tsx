import { type InputHTMLAttributes, useId } from "react";
import { cn } from "../utils/cn";

export const inputClass =
  "w-full rounded-xl border border-white/12 bg-canvas p-3.5 text-base text-fg placeholder:text-faint focus:border-brand-warm/60 focus:outline-none";

export function TextField({
  label,
  hint,
  className,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={inputId} className="text-sm text-fg-2">
        {label}
      </label>
      <input id={inputId} className={inputClass} {...props} />
      {hint ? <span className="text-xs text-muted">{hint}</span> : null}
    </div>
  );
}
