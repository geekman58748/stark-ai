import { errorCopy, useTopUp } from "@stark/api";
import { AmountField } from "@stark/ui/amount-field";
import { Button } from "@stark/ui/button";
import { Card } from "@stark/ui/card";
import { Eyebrow } from "@stark/ui/eyebrow";
import { RadioList, RadioRow } from "@stark/ui/radio-row";
import { formatNaira } from "@stark/utils/format";
import { requestId } from "@stark/utils/id";
import { useMemo, useState } from "react";

export const fundMethods = [
  {
    id: "bank",
    name: "Bank transfer",
    note: "Recommended · lands in minutes",
    source: "Bank transfer",
    detail: "You’ll get your own account number to send to.",
  },
  {
    id: "card",
    name: "Debit card",
    note: "Visa, Mastercard, Verve",
    source: "Debit card",
    detail: "You’ll confirm the payment in your bank app.",
  },
  {
    id: "crypto",
    name: "I already have crypto",
    note: "Send almost any coin",
    source: "Crypto deposit",
    detail: "Whatever you send is changed into naira in your Stark balance.",
  },
] as const;

export type FundMethod = (typeof fundMethods)[number]["id"];

/**
 * Adds money to the balance. Today this credits the demo ledger straight away: there is no
 * bank or card processor behind it yet, and the copy says so rather than pretending.
 */
export function FundForm({
  initialMethod = "bank",
  onDone,
}: {
  initialMethod?: FundMethod;
  onDone: () => void;
}) {
  const [amount, setAmount] = useState(20000);
  const [method, setMethod] = useState<FundMethod>(initialMethod);
  const topUp = useTopUp();
  // One id per amount + method: a double tap on a flaky connection can't credit twice.
  const key = useMemo(() => requestId("dep"), [amount, method]);
  const current = fundMethods.find((m) => m.id === method)!;

  return (
    <div className="flex flex-col gap-6">
      <AmountField
        label="Amount"
        value={amount}
        onChange={setAmount}
        presets={[10000, 20000, 50000]}
      />
      <RadioList label="How to pay">
        {fundMethods.map((m) => (
          <RadioRow
            key={m.id}
            checked={m.id === method}
            onSelect={() => setMethod(m.id)}
            title={m.name}
            subtitle={m.note}
          />
        ))}
      </RadioList>
      <Card className="gap-2.5">
        <Eyebrow>{current.name}</Eyebrow>
        <span className="text-[15px]">{current.detail}</span>
        <span className="text-xs text-muted">
          Demo mode: the money shows up in your balance straight away.
        </span>
      </Card>
      {topUp.error ? (
        <p role="alert" className="m-0 text-[13px] text-brand-soft">
          {errorCopy(topUp.error)}
        </p>
      ) : null}
      <Button
        size="lg"
        block
        disabled={amount <= 0 || topUp.isPending}
        onClick={() =>
          topUp.mutate(
            { amount_ngn: amount, request_id: key, source: current.source },
            { onSuccess: onDone },
          )
        }
      >
        {topUp.isPending ? "Adding…" : `Add ${formatNaira(amount)}`}
      </Button>
    </div>
  );
}
