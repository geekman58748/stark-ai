import type { Plan } from "@stark/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@stark/ui/components/select";
import { formatNaira } from "@stark/utils/format";

export function PlanSelect({
  id,
  plans,
  provider,
  value,
  onChange,
  disabled,
}: {
  id?: string;
  plans: Plan[] | undefined;
  provider: string;
  value: string | undefined;
  onChange: (plan: string) => void;
  disabled?: boolean;
}) {
  const index = plans?.findIndex((p) => p.plan === value) ?? -1;
  const placeholder = !plans
    ? "Loading plans…"
    : plans.length
      ? "Choose a plan"
      : `No plans for ${provider} yet`;

  const handlePlanChange = (i: string | null) => {
    if (i !== null && plans) onChange(plans[Number(i)]!.plan);
  };

  return (
    <Select
      items={plans?.map((p, i) => ({ value: String(i), label: p.label }))}
      value={index === -1 ? null : String(index)}
      onValueChange={handlePlanChange}
      disabled={disabled || !plans?.length}
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="max-h-80">
        {plans?.map((p, i) => (
          <SelectItem key={`${p.provider}-${p.plan}-${i}`} value={String(i)}>
            <span className="truncate">{p.label}</span>
            <span className="tabular ml-auto pl-3 text-muted-foreground">
              {formatNaira(p.price_ngn)}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
