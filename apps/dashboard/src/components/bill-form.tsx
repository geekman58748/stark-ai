import { type Bill, type BillKind, errorCopy, plansQuery, useAddBill } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { ChipGroup, ChoiceChip } from "@stark/ui/components/choice-chip";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@stark/ui/components/field";
import { Icons } from "@stark/ui/components/icons";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@stark/ui/components/select";
import { Spinner } from "@stark/ui/components/spinner";
import { TextField } from "@stark/ui/components/text-field";
import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { PlanSelect } from "@/components/plan-select";
import { billKinds, defaultNickname, providers, referenceLabel } from "@/lib/bills";

/** Pick a bill type, enter its number, choose a plan when it's sold as one, name it. */
export function BillForm({
  onAdded,
  submitLabel = "Add bill",
  footer,
}: {
  onAdded: (bill: Bill) => void;
  submitLabel?: string;
  footer?: ReactNode;
}) {
  const [kind, setKind] = useState<BillKind>("electricity");
  const [provider, setProvider] = useState(providers.electricity[0]!);
  const [reference, setReference] = useState("");
  const [label, setLabel] = useState(defaultNickname.electricity);
  const [plan, setPlan] = useState<string>();
  const addBill = useAddBill();
  const providerId = useId();
  const planId = useId();

  const sellsPlans = kind === "data" || kind === "tv";
  const plans = useQuery({
    ...plansQuery(sellsPlans ? kind : undefined, provider),
    enabled: sellsPlans,
  });

  function pickKind(next: BillKind) {
    setKind(next);
    setProvider(providers[next][0]!);
    setLabel(defaultNickname[next]);
    setPlan(undefined);
    addBill.reset();
  }

  return (
    <form
      className="m-0"
      onSubmit={(e) => {
        e.preventDefault();
        addBill.mutate(
          {
            kind,
            provider,
            reference: reference.replace(/\s+/g, ""),
            label: label.trim() || undefined,
            plan,
          },
          { onSuccess: onAdded },
        );
      }}
    >
      <FieldGroup className="gap-6">
        <ChipGroup label="Bill type" columns={3}>
          {billKinds.map((k) => (
            <ChoiceChip
              key={k.kind}
              selected={k.kind === kind}
              onClick={() => pickKind(k.kind)}
              className="text-sm"
            >
              {k.label}
            </ChoiceChip>
          ))}
        </ChipGroup>

        <Field>
          <FieldLabel htmlFor={providerId} className="font-normal text-fg-2">
            Provider
          </FieldLabel>
          <Select
            value={provider}
            onValueChange={(next) => {
              if (next === null) return;
              setProvider(next);
              setPlan(undefined);
            }}
          >
            <SelectTrigger id={providerId} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {providers[kind].map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <TextField
          label={referenceLabel[kind]}
          inputMode="numeric"
          autoComplete="off"
          required
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          className="[&_input]:tabular [&_input]:tracking-[0.04em]"
        />

        {sellsPlans ? (
          <Field>
            <FieldLabel htmlFor={planId} className="font-normal text-fg-2">
              Plan
            </FieldLabel>
            <PlanSelect
              id={planId}
              plans={plans.data}
              provider={provider}
              value={plan}
              onChange={setPlan}
            />
          </Field>
        ) : null}

        <TextField label="Call it" value={label} onChange={(e) => setLabel(e.target.value)} />

        {kind === "internet" || kind === "water" ? (
          <FieldDescription className="text-[13px]">
            You can save this now. Stark will start paying it once the provider is connected.
          </FieldDescription>
        ) : null}

        {footer}

        {addBill.error ? (
          <FieldError className="flex items-center gap-2 text-[13px]">
            <Icons.Warning size={16} />
            {errorCopy(addBill.error)}
          </FieldError>
        ) : null}

        <Button
          type="submit"
          size="lg"
          block
          disabled={addBill.isPending || !reference.trim() || (sellsPlans && !plan)}
        >
          {addBill.isPending ? <Spinner /> : null}
          {addBill.isPending ? "Adding…" : submitLabel}
        </Button>
      </FieldGroup>
    </form>
  );
}
