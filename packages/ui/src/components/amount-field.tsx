import { ChipGroup, ChoiceChip } from "@stark/ui/components/choice-chip";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@stark/ui/components/input-group";
import { Label } from "@stark/ui/components/label";
import { cn } from "@stark/ui/utils/cn";
import { formatAmountInput, parseAmountInput } from "@stark/utils/format";
import { useId } from "react";

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
      <Label htmlFor={id} className="font-normal text-fg-2">
        {label}
      </Label>
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
    </div>
  );
}
