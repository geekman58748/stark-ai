import { formatAmountInput, parseAmountInput } from "@stark/utils/format";
import { useId } from "react";
import { cn } from "../utils/cn";
import { ChipGroup, ChoiceChip } from "./choice-chip";

/**
 * A typed naira amount plus quick-pick chips. This is how every amount, cap and threshold
 * is set in Stark: there are no sliders anywhere in the product.
 */
export function AmountField({
  label,
  value,
  onChange,
  presets,
  className,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  presets?: number[];
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      <label htmlFor={id} className="text-sm text-fg-2">
        {label}
      </label>
      <div className="flex items-center gap-2 rounded-xl border border-white/12 bg-canvas px-3.5 focus-within:border-brand-warm/60">
        <span aria-hidden="true" className="font-serif text-2xl text-muted">
          ₦
        </span>
        <input
          id={id}
          inputMode="numeric"
          autoComplete="off"
          value={formatAmountInput(value)}
          onChange={(e) => onChange(parseAmountInput(e.target.value))}
          className="tabular w-full bg-transparent py-3 font-serif text-[28px] text-fg focus:outline-none"
        />
      </div>
      {presets?.length ? (
        <ChipGroup label={`Quick amounts for ${label.toLowerCase()}`}>
          {presets.map((p) => (
            <ChoiceChip key={p} size="sm" selected={p === value} onClick={() => onChange(p)}>
              ₦{formatAmountInput(p)}
            </ChoiceChip>
          ))}
        </ChipGroup>
      ) : null}
    </div>
  );
}
