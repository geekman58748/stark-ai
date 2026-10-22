import { activityQuery, stateQuery } from "@stark/api";
import { buttonVariants } from "@stark/ui/button";
import { Card } from "@stark/ui/card";
import { cn } from "@stark/ui/cn";
import { Eyebrow } from "@stark/ui/eyebrow";
import { IconTile } from "@stark/ui/icon-tile";
import { Icons } from "@stark/ui/icons";
import { RowList } from "@stark/ui/list-row";
import { Notice } from "@stark/ui/notice";
import { SectionHeading } from "@stark/ui/section-heading";
import { Stat, StatGrid } from "@stark/ui/stat";
import { StatusPill } from "@stark/ui/status-pill";
import { formatNaira, greeting } from "@stark/utils/format";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ActivityRow } from "@/components/activity-row";
import { BillRow } from "@/components/bill-row";
import { LOW_DAYS, meterBill } from "@/lib/bills";

export const Route = createFileRoute("/_app/")({
  loader: ({ context }) => {
    context.queryClient.prefetchQuery(activityQuery());
  },
  head: () => ({ meta: [{ title: "Home · Stark" }] }),
  component: Home,
});

function runway(balance: number, spentThisMonth: number) {
  if (spentThisMonth <= 0) return "ready for your bills";
  const months = Math.floor(balance / spentThisMonth);
  if (months < 1) return "less than a month of bills";
  return `enough for about ${months} month${months === 1 ? "" : "s"} of bills`;
}

function Home() {
  const { data: state } = useSuspenseQuery(stateQuery());
  const { data: activity } = useQuery(activityQuery());
  const meter = meterBill(state);
  const low = meter && state.days_left !== null && state.days_left <= LOW_DAYS;

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <span className="text-[13px] text-muted">
          {greeting()}, {state.first_name}
        </span>
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
            {low ? "One thing needs you" : "Everything’s covered"}
          </h1>
          <StatusPill>Stark is on</StatusPill>
        </div>
      </div>

      <Card>
        <Eyebrow>Balance</Eyebrow>
        <div className="flex flex-wrap items-baseline gap-2.5">
          <span className="font-serif text-5xl leading-none">{formatNaira(state.balance_ngn)}</span>
          <span className="text-xs text-muted">{runway(state.balance_ngn, state.spent_ngn)}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/wallet/add" className={cn(buttonVariants(), "hover:text-white")}>
            Add money
          </Link>
          <Link
            to="/wallet"
            className={cn(buttonVariants({ variant: "secondary" }), "hover:text-fg")}
          >
            Withdraw
          </Link>
        </div>
        <StatGrid>
          <Stat label="Spent this month">
            {formatNaira(state.spent_ngn)} of {formatNaira(state.cap_ngn)}
          </Stat>
          <Stat label="Limit left">{formatNaira(state.remaining_cap_ngn)}</Stat>
          {meter && state.days_left !== null ? (
            <Stat label={meter.label}>About {state.days_left} days left</Stat>
          ) : null}
          <Stat label="Bills">{state.bills.length} active</Stat>
        </StatGrid>
      </Card>

      {low && meter ? (
        <Notice
          icon={
            <IconTile>
              <Icons.Electricity size={16} />
            </IconTile>
          }
          title={`${meter.label} meter is running low`}
          actions={
            <>
              <Link
                to="/pay"
                search={{ bill: meter.id, amount: meter.last_amount_ngn ?? undefined }}
                className={cn(buttonVariants(), "hover:text-white")}
              >
                Top up {meter.last_amount_ngn ? formatNaira(meter.last_amount_ngn) : ""}
              </Link>
              <Link
                to="/bills"
                className={cn(buttonVariants({ variant: "secondary" }), "hover:text-fg")}
              >
                Later
              </Link>
            </>
          }
        >
          About {state.days_left} days left at your usual use.
        </Notice>
      ) : null}

      <AskStark />

      <SectionHeading
        action={
          <Link to="/bills" className="text-xs no-underline">
            See all
          </Link>
        }
      >
        Your bills
      </SectionHeading>
      {state.bills.length ? (
        <RowList>
          {state.bills.slice(0, 4).map((bill) => (
            <BillRow key={bill.id} bill={bill} state={state} />
          ))}
        </RowList>
      ) : (
        <EmptyBills />
      )}

      <SectionHeading
        action={
          <Link to="/activity" className="text-xs no-underline">
            See all
          </Link>
        }
      >
        Recent activity
      </SectionHeading>
      <RowList>
        {activity?.slice(0, 3).map((r) => (
          <ActivityRow key={r.id} receipt={r} />
        ))}
      </RowList>
    </>
  );
}

function AskStark() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  return (
    <form
      className="m-0 flex items-center gap-2 rounded-full border border-white/10 bg-surface py-1.5 pr-1.5 pl-[18px]"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) navigate({ to: "/talk", search: { q: text.trim() } });
      }}
    >
      <label htmlFor="ask" className="sr-only">
        Ask Stark
      </label>
      <input
        id="ask"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ask Stark: “buy 2GB for my line”"
        className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-fg placeholder:text-muted focus:outline-none"
      />
      {text.trim() ? (
        <button
          type="submit"
          aria-label="Send"
          className="flex size-10 cursor-pointer items-center justify-center rounded-full border-0 bg-brand text-white"
        >
          <Icons.ArrowRight size={18} />
        </button>
      ) : (
        <Link
          to="/talk"
          aria-label="Speak instead"
          className="flex size-10 items-center justify-center rounded-full bg-brand text-white hover:text-white"
        >
          <Icons.Mic size={18} />
        </Link>
      )}
    </form>
  );
}

function EmptyBills() {
  return (
    <Link
      to="/bills/new"
      className="flex items-center justify-center gap-2 rounded-row border border-dashed border-white/12 p-4 text-[13px] text-fg-2 no-underline hover:text-fg"
    >
      <Icons.Add size={16} />
      Add your first bill
    </Link>
  );
}
