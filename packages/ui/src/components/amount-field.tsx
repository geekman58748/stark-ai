import { ChipGroup, ChoiceChip } from "@stark/ui/components/choice-chip";
import { Field, FieldError, FieldLabel } from "@stark/ui/components/field";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@stark/ui/components/input-group";
import { cn } from "@stark/ui/utils/cn";
import { formatAmountInput, parseAmountInput } from "@stark/utils/format";
import { type ReactNode, useId } from "react";

/**
 * A typed naira amount plus quick-pick chips. This is how every amount, cap and threshold
 * is set in Stark: there are no sliders anywhere in the product.
 */
export function AmountField({
  label,
  value,
  onChange,
  presets,
  error,
  className,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  presets?: number[];
  error?: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <Field data-invalid={error ? true : undefined} className={cn("gap-2.5", className)}>
      <FieldLabel htmlFor={id} className="font-normal text-fg-2">
        {label}
      </FieldLabel>
      <InputGroup className="h-auto rounded-xl px-1.5 dark:bg-canvas">
        <InputGroupAddon>
          <span aria-hidden="true" className="font-serif text-2xl text-muted-foreground">
            ₦
          </span>
        </InputGroupAddon>
        <InputGroupInput
          id={id}
          inputMode="numeric"
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          value={formatAmountInput(value)}
          onChange={(e) => onChange(parseAmountInput(e.target.value))}
          className="tabular h-auto py-3 font-serif text-[28px] md:text-[28px]"
        />
      </InputGroup>
      {presets?.length ? (
        <ChipGroup label={`Quick amounts for ${label.toLowerCase()}`}>
          {presets.map((p) => (
            <ChoiceChip key={p} size="sm" selected={p === value} onClick={() => onChange(p)}>
              ₦{formatAmountInput(p)}
            </ChoiceChip>
          ))}
        </ChipGroup>
      ) : null}
      <FieldError>{error}</FieldError>
    </Field>
  );
}
