import type { ReactNode } from "react";

export function Field({
  label,
  type = "text",
  autoComplete,
  placeholder,
  trailing,
  value,
  onChange,
  required,
}: {
  label: string;
  type?: string;
  autoComplete?: string;
  placeholder?: string;
  trailing?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="group flex items-center gap-3 rounded-xl border border-line-2 bg-white/[0.028] px-3.5 py-2.5 transition-colors hover:border-white/15 focus-within:border-brand focus-within:ring-3 focus-within:ring-brand/25">
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-[10px] font-medium tracking-[0.07em] text-faint uppercase transition-colors group-focus-within:text-brand/90">
          {label}
        </span>
        <input
          type={type}
          autoComplete={autoComplete}
          placeholder={placeholder}
          required={required}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full min-w-0 bg-transparent text-[15px] leading-6 text-fg outline-none placeholder:text-faint/70"
        />
      </span>
      {trailing}
    </label>
  );
}
