import { errorCopy, limitsQuery, useResetDemo, useUpdateLimits } from "@stark/api";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { Icons } from "@stark/ui/components/icons";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { formatNaira } from "@stark/utils/format";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageTitle } from "@/components/app-shell";

export const Route = createFileRoute("/_app/settings")({
  loader: ({ context }) => context.queryClient.ensureQueryData(limitsQuery()),
  head: () => ({ meta: [{ title: "Settings · Stark" }] }),
  component: Settings,
});

function Settings() {
  const { data: limits } = useSuspenseQuery(limitsQuery());
  const [monthly, setMonthly] = useState(limits.monthly_cap_ngn);
  const [per, setPer] = useState(limits.per_payment_cap_ngn);
  const update = useUpdateLimits();
  const dirty = monthly !== limits.monthly_cap_ngn || per !== limits.per_payment_cap_ngn;
  const invalid = monthly <= 0 || per <= 0 || per > monthly;

  return (
    <>
      <PageTitle>Settings</PageTitle>

      <SectionHeading>Spending limits</SectionHeading>
      <Card className="gap-5">
        <AmountField
          label="Most Stark can spend in a month"
          value={monthly}
          onChange={(v) => {
            update.reset();
            setMonthly(v);
          }}
          presets={[20000, 30000, 50000, 100000]}
        />
        <AmountField
          label="Most it can spend at once"
          value={per}
          onChange={(v) => {
            update.reset();
            setPer(v);
          }}
          presets={[5000, 10000, 20000]}
        />
        <p className="m-0 text-[13px] text-fg-2">
          If a request goes over, Stark says no and offers the most it can pay instead. Nobody, not
          even Stark, can raise these but you. You’ve spent {formatNaira(limits.spent_ngn)} this
          month.
        </p>
        {per > monthly ? (
          <p className="m-0 text-[13px] text-brand-soft">
            A single payment can’t be more than the monthly limit.
          </p>
        ) : null}
        {update.error ? (
          <p role="alert" className="m-0 text-[13px] text-brand-soft">
            {errorCopy(update.error)}
          </p>
        ) : null}
        {update.isSuccess && !dirty ? (
          <p aria-live="polite" className="m-0 flex items-center gap-2 text-[13px] text-fg-2">
            <Icons.Check size={16} className="text-brand-warm" />
            Saved. Stark uses the new limits from its next payment.
          </p>
        ) : null}
        {dirty ? (
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={invalid || update.isPending}
              onClick={() => update.mutate({ monthly_cap_ngn: monthly, per_payment_cap_ngn: per })}
            >
              Save {formatNaira(monthly)} a month, {formatNaira(per)} at once
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setMonthly(limits.monthly_cap_ngn);
                setPer(limits.per_payment_cap_ngn);
              }}
            >
              Undo
            </Button>
          </div>
        ) : null}
      </Card>

      <SectionHeading>How Stark listens</SectionHeading>
      <Card className="gap-2">
        <span className="font-medium">Telegram and the wall phone</span>
        <p className="m-0 text-[13px] text-fg-2">
          Voice notes only count when they include the word “Stark”, so everyday talk in the room
          never triggers a payment.
        </p>
      </Card>

      {import.meta.env.DEV ? <ResetDemo /> : null}
    </>
  );
}

function ResetDemo() {
  const reset = useResetDemo();
  const [confirming, setConfirming] = useState(false);
  return (
    <Card className="flex-row flex-wrap items-center gap-3">
      <span className="flex flex-[1_1_240px] flex-col">
        <span className="font-medium">Reset the demo</span>
        <span className="text-[13px] text-muted-foreground">
          Puts the seeded bills, balance and history back. Bills you added are removed.
        </span>
      </span>
      {confirming ? (
        <Button
          disabled={reset.isPending}
          onClick={() => reset.mutate(undefined, { onSettled: () => setConfirming(false) })}
        >
          Yes, reset
        </Button>
      ) : (
        <Button variant="secondary" onClick={() => setConfirming(true)}>
          Reset
        </Button>
      )}
    </Card>
  );
}
