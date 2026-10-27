import { PlanSelect } from "@/components/bills/plan-select";
import type { Plan } from "@stark/api";
import { Field, FieldLabel } from "@stark/ui/components/field";
import { useId } from "react";

export function PlanField({
  plans,
  provider,
  value,
  onChange,
}: {
  plans: Plan[] | undefined;
  provider: string;
  value: string | undefined;
  onChange: (plan: string) => void;
}) {
  const planId = useId();
  return (
    <Field>
      <FieldLabel htmlFor={planId} className="font-normal text-fg-2">
        Plan
      </FieldLabel>
      <PlanSelect
        id={planId}
        plans={plans}
        provider={provider}
        value={value}
        onChange={onChange}
      />
    </Field>
  );
}
