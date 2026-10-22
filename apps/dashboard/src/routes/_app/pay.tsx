import { BackLink, PageTitle } from "@/components/app-shell";
import { TokenLine } from "@/components/token-card";
import { billStatus, fixedAmount, isPayable, kindLabel } from "@/lib/bills";
import {
  type Bill,
  errorCopy,
  isApiError,
  limitsQuery,
  type Receipt,
  stateQuery,
  usePayBill,
} from "@stark/api";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button, buttonVariants } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { RadioList, RadioRow } from "@stark/ui/components/radio-row";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { cn } from "@stark/ui/utils/cn";
import { formatNaira } from "@stark/utils/format";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";

export const Route = createFileRoute("/_app/pay")({
  validateSearch: z.object({
    bill: z.string().optional(),
    amount: z.number().int().positive().optional(),
  }),
  loader: ({ context }) =>
    context.queryClient.query({ ...limitsQuery(), staleTime: "static" }),
  head: () => ({ meta: [{ title: "Pay a bill · Stark" }] }),
  component: Pay,
});

function Pay() {
  const { data: state } = useSuspenseQuery(stateQuery());
  const { data: limits } = useSuspenseQuery(limitsQuery());
  const search = Route.useSearch();
  const payable = state.bills.filter(isPayable);

  const [billId, setBillId] = useState(search.bill ?? payable[0]?.id);
  const bill = payable.find((b) => b.id === billId);
  const [typed, setTyped] = useState(search.amount ?? 5000);
  const amount = bill ? (fixedAmount(bill) ?? typed) : typed;
  const pay = usePayBill();

  const presets = [2000, 5000, limits.remaining_cap_ngn]
    .filter((v, i, a) => v > 0 && a.indexOf(v) === i)
    .sort((a, b) => a - b);

  const hint =
    amount > limits.per_payment_cap_ngn
      ? `That’s over your ${formatNaira(limits.per_payment_cap_ngn)} limit for one payment.`
      : amount > limits.remaining_cap_ngn
        ? `You have ${formatNaira(limits.remaining_cap_ngn)} left of this month’s limit.`
        : amount > state.balance_ngn
          ? `Your wallet has ${formatNaira(state.balance_ngn)}.`
          : null;

  if (!payable.length) {
    return (
      <>
        <BackLink to="/">Home</BackLink>
        <PageTitle>Pay a bill</PageTitle>
        <p className="m-0 text-fg-2">
          Add a bill first, then Stark can pay it.
        </p>
        <Link
          to="/bills/new"
          className={cn(buttonVariants(), "self-start hover:text-white")}
        >
          Add a bill
        </Link>
      </>
    );
  }

  const choose = (fn: () => void) => () => {
    pay.reset();
    fn();
  };

  return (
    <div className="flex w-full max-w-140 flex-col gap-5 self-center">
      <BackLink to="/">Home</BackLink>
      <PageTitle>Pay a bill</PageTitle>

      <RadioList
        label="Which bill"
        value={billId}
        onValueChange={(id) => choose(() => setBillId(id))()}
      >
        {payable.map((b) => (
          <RadioRow
            key={b.id}
            value={b.id}
            title={b.label}
            subtitle={`${kindLabel(b.kind)} · ${billStatus(b, state).text}`}
          />
        ))}
      </RadioList>

      {bill && fixedAmount(bill) ? (
        <Card className="flex-row items-center gap-3 p-4">
          <span className="flex flex-1 flex-col">
            <span className="font-medium">{formatNaira(amount)}</span>
            <span className="text-xs text-muted-foreground">
              The {bill.provider} plan price. Plans can’t be part-paid.
            </span>
          </span>
        </Card>
      ) : (
        <AmountField
          label="Amount"
          value={typed}
          onChange={(v) => choose(() => setTyped(v))()}
          presets={presets}
        />
      )}

      {pay.data ? (
        <Result receipt={pay.data} bill={bill} onAgain={() => pay.reset()} />
      ) : (
        <Card>
          <StatGrid>
            <Stat label="From">Your wallet</Stat>
            <Stat label="Left this month after">
              {formatNaira(Math.max(0, limits.remaining_cap_ngn - amount))}
            </Stat>
          </StatGrid>
          {hint ? (
            <p className="m-0 flex items-center gap-2 text-[13px] text-brand-soft">
              <Icons.Warning size={16} />
              {hint}
            </p>
          ) : (
            <p className="m-0 flex items-center gap-2 text-[13px] text-fg-2">
              <Icons.Shield size={16} className="text-brand-warm" />
              Within your spending limits
            </p>
          )}
          {pay.error ? (
            <Refused
              error={pay.error}
              onPay={(v) => {
                setTyped(v);
                pay.reset();
              }}
            />
          ) : null}
          <Button
            size="lg"
            block
            disabled={!bill || amount <= 0 || pay.isPending}
            onClick={() =>
              bill && pay.mutate({ bill_id: bill.id, amount_ngn: amount })
            }
          >
            {pay.isPending ? "Paying…" : `Pay ${formatNaira(amount)}`}
          </Button>
        </Card>
      )}
    </div>
  );
}

/** A refusal explains the rule that stopped it, and offers what Stark can pay instead. */
function Refused({
  error,
  onPay,
}: {
  error: Error;
  onPay: (amount: number) => void;
}) {
  const { data: limits } = useSuspenseQuery(limitsQuery());
  const offer = isApiError(error, "over_per_payment_cap")
    ? limits.per_payment_cap_ngn
    : isApiError(error, "over_cap")
      ? limits.remaining_cap_ngn
      : null;
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-row border border-brand-warm/40 bg-brand-wash p-3.5"
    >
      <span className="text-[13px]">{errorCopy(error)}</span>
      {offer ? (
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => onPay(offer)}
        >
          Pay {formatNaira(offer)} instead
        </Button>
      ) : null}
    </div>
  );
}

function Result({
  receipt,
  bill,
  onAgain,
}: {
  receipt: Receipt;
  bill?: Bill;
  onAgain: () => void;
}) {
  const delivered = receipt.status === "delivered";
  const title = delivered
    ? receipt.token
      ? "Paid. Here’s your token."
      : `Paid. ${bill?.label ?? "Your bill"} is topped up.`
    : receipt.status === "pending"
      ? "Still going through"
      : "That didn’t go through";
  const body = delivered
    ? receipt.token
      ? "Type it into your meter keypad."
      : null
    : receipt.status === "pending"
      ? "The provider is still processing it. You haven’t been charged yet, and Stark won’t buy twice."
      : "The provider refused it. Nothing was charged.";

  return (
    <Card aria-live="polite">
      <div className="flex items-center gap-3">
        <IconTile>
          {delivered ? <Icons.Check size={16} /> : <Icons.Clock size={16} />}
        </IconTile>
        <span className="font-serif text-2xl">{title}</span>
      </div>
      {receipt.token ? <TokenLine token={receipt.token} /> : null}
      {body ? (
        <span className="text-xs text-muted-foreground">{body}</span>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Link to="/" className={cn(buttonVariants(), "hover:text-white")}>
          Done
        </Link>
        <Button variant="secondary" onClick={onAgain}>
          Pay another bill
        </Button>
      </div>
    </Card>
  );
}
