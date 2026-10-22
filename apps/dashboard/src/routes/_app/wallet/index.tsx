import { activityQuery, errorCopy, useWithdraw, walletQuery } from "@stark/api";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button, buttonVariants } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { listRowClass, RowList, RowText } from "@stark/ui/components/list-row";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { cn } from "@stark/ui/utils/cn";
import { formatNaira } from "@stark/utils/format";
import { requestId } from "@stark/utils/id";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ActivityRow } from "@/components/activity-row";
import { PageTitle } from "@/components/app-shell";

export const Route = createFileRoute("/_app/wallet/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(walletQuery()),
      context.queryClient.ensureQueryData(activityQuery()),
    ]),
  head: () => ({ meta: [{ title: "Wallet · Stark" }] }),
  component: WalletPage,
});

const ways = [
  { method: "bank", title: "Bank transfer", subtitle: "Your own account number", icon: Icons.Bank },
  { method: "card", title: "Debit card", subtitle: "Visa, Mastercard, Verve", icon: Icons.Card },
  { method: "crypto", title: "Crypto", subtitle: "Send almost any coin", icon: Icons.Coins },
] as const;

function WalletPage() {
  const { data: wallet } = useSuspenseQuery(walletQuery());
  const { data: activity } = useSuspenseQuery(activityQuery());
  const [withdrawing, setWithdrawing] = useState(false);
  const moves = activity.filter((r) => r.type === "deposit" || r.type === "withdrawal");

  return (
    <>
      <PageTitle>Wallet</PageTitle>
      <Card>
        <Eyebrow>Available</Eyebrow>
        <div className="flex flex-wrap items-baseline gap-2.5">
          <span className="font-serif text-5xl leading-none">
            {formatNaira(wallet.balance_ngn)}
          </span>
          <span className="text-xs text-muted-foreground">ready for your bills</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/wallet/add" className={cn(buttonVariants(), "hover:text-white")}>
            Add money
          </Link>
          <Button
            variant="secondary"
            aria-expanded={withdrawing}
            onClick={() => setWithdrawing((v) => !v)}
          >
            Withdraw to bank
          </Button>
        </div>
        {withdrawing ? (
          <Withdraw max={wallet.balance_ngn} onDone={() => setWithdrawing(false)} />
        ) : null}
        <StatGrid>
          <Stat label="Added this month">{formatNaira(wallet.added_this_month_ngn)}</Stat>
          <Stat label="Spent this month">{formatNaira(wallet.spent_ngn)}</Stat>
          <Stat label="Monthly limit left">{formatNaira(wallet.remaining_cap_ngn)}</Stat>
          <Stat label="Pays from">This wallet</Stat>
        </StatGrid>
      </Card>

      <SectionHeading>Ways to add money</SectionHeading>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {ways.map(({ method, title, subtitle, icon: Icon }) => (
          <Link
            key={method}
            to="/wallet/add"
            search={{ method }}
            className={cn(
              listRowClass,
              "flex-nowrap gap-3 hover:text-fg sm:flex-col sm:items-start sm:gap-2.5 sm:p-4",
            )}
          >
            <IconTile>
              <Icon size={16} />
            </IconTile>
            <RowText title={title} subtitle={subtitle} className="flex-none sm:flex-none" />
          </Link>
        ))}
      </div>

      <SectionHeading>Money in and out</SectionHeading>
      <RowList>
        {moves.map((r) => (
          <ActivityRow key={r.id} receipt={r} />
        ))}
        {!moves.length ? (
          <p className="m-0 text-[13px] text-muted-foreground">No money in or out yet.</p>
        ) : null}
      </RowList>
    </>
  );
}

function Withdraw({ max, onDone }: { max: number; onDone: () => void }) {
  const [amount, setAmount] = useState(Math.min(10000, max));
  const withdraw = useWithdraw();
  const key = useMemo(() => requestId("wd"), [amount]);
  return (
    <div className="flex flex-col gap-3 rounded-row border border-line bg-canvas p-4">
      <AmountField
        label="Send to your bank"
        value={amount}
        onChange={setAmount}
        presets={[5000, 10000, max].filter((v, i, a) => v > 0 && v <= max && a.indexOf(v) === i)}
      />
      {withdraw.error ? (
        <p role="alert" className="m-0 text-[13px] text-brand-soft">
          {errorCopy(withdraw.error)}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={amount <= 0 || withdraw.isPending}
          onClick={() =>
            withdraw.mutate({ amount_ngn: amount, request_id: key }, { onSuccess: onDone })
          }
        >
          {withdraw.isPending ? "Sending…" : `Withdraw ${formatNaira(amount)}`}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
