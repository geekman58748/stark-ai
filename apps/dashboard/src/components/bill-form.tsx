import { type Bill, type BillKind, errorCopy, plansQuery, useAddBill } from "@stark/api";
import { Button } from "@stark/ui/button";
import { ChipGroup, ChoiceChip } from "@stark/ui/choice-chip";
import { Icons } from "@stark/ui/icons";
import { RadioList, RadioRow } from "@stark/ui/radio-row";
import { inputClass, TextField } from "@stark/ui/text-field";
import { formatNaira } from "@stark/utils/format";
import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
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
      className="m-0 flex flex-col gap-6"
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

      <div className="flex flex-col gap-1.5">
        <label htmlFor={providerId} className="text-sm text-fg-2">
          Provider
        </label>
        <select
          id={providerId}
          value={provider}
          onChange={(e) => {
            setProvider(e.target.value);
            setPlan(undefined);
          }}
          className={inputClass}
        >
          {providers[kind].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </div>

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
        <div className="flex flex-col gap-2">
          <span className="text-sm text-fg-2">Plan</span>
          {plans.isPending ? <span className="text-[13px] text-muted">Loading plans…</span> : null}
          {plans.data && !plans.data.length ? (
            <span className="text-[13px] text-muted">No plans for {provider} yet.</span>
          ) : null}
          <RadioList label="Plan">
            <div className="flex max-h-72 flex-col gap-2 overflow-y-auto pr-1">
              {plans.data?.map((p, i) => (
                <RadioRow
                  // The vendor catalogue repeats some plan codes across services.
                  key={`${p.provider}-${p.plan}-${i}`}
                  checked={p.plan === plan}
                  onSelect={() => setPlan(p.plan)}
                  title={p.label}
                  subtitle={formatNaira(p.price_ngn)}
                />
              ))}
            </div>
          </RadioList>
        </div>
      ) : null}

      <TextField label="Call it" value={label} onChange={(e) => setLabel(e.target.value)} />

      {kind === "internet" || kind === "water" ? (
        <p className="m-0 text-[13px] text-muted">
          You can save this now. Stark will start paying it once the provider is connected.
        </p>
      ) : null}

      {footer}

      {addBill.error ? (
        <p role="alert" className="m-0 flex items-center gap-2 text-[13px] text-brand-soft">
          <Icons.Warning size={16} />
          {errorCopy(addBill.error)}
        </p>
      ) : null}

      <Button
        type="submit"
        size="lg"
        block
        disabled={addBill.isPending || !reference.trim() || (sellsPlans && !plan)}
      >
        {addBill.isPending ? "Adding…" : submitLabel}
      </Button>
    </form>
  );
}
