import {
  activityQuery,
  type Bill,
  billQuery,
  errorCopy,
  plansQuery,
  type Receipt,
  stateQuery,
  useDeleteBill,
  useUpdateBill,
} from "@stark/api";
import { Button, buttonVariants } from "@stark/ui/button";
import { Card } from "@stark/ui/card";
import { cn } from "@stark/ui/cn";
import { Eyebrow } from "@stark/ui/eyebrow";
import { RowList } from "@stark/ui/list-row";
import { pillTabClass } from "@stark/ui/pill-tabs";
import { RadioList, RadioRow } from "@stark/ui/radio-row";
import { SectionHeading } from "@stark/ui/section-heading";
import { Stat, StatGrid } from "@stark/ui/stat";
import { StatusPill } from "@stark/ui/status-pill";
import { inputClass } from "@stark/ui/text-field";
import { formatLongDate, formatNaira, formatShortDate, maskReference } from "@stark/utils/format";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { BackLink } from "@/components/app-shell";
import { BillIcon } from "@/components/bill-row";
import { TokenLine } from "@/components/token-card";
import { billStatus, isPayable, kindLabel, meterBill } from "@/lib/bills";

export const Route = createFileRoute("/_app/bills/$billId")({
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.ensureQueryData(billQuery(params.billId)),
      context.queryClient.ensureQueryData(activityQuery()),
    ]),
  head: () => ({ meta: [{ title: "Bill · Stark" }] }),
  component: BillDetail,
});

function BillDetail() {
  const { billId } = Route.useParams();
  const { data: bill } = useSuspenseQuery(billQuery(billId));
  const { data: state } = useSuspenseQuery(stateQuery());
  const { data: activity } = useSuspenseQuery(activityQuery());
  const [editing, setEditing] = useState<"menu" | "rename" | "plan" | "remove" | null>(null);

  const history = activity.filter((r) => r.bill_id === bill.id);
  const status = billStatus(bill, state);
  const firstPaid = history.at(-1)?.created_at;

  return (
    <>
      <BackLink to="/bills">Bills</BackLink>
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-3">
          <BillIcon bill={bill} />
          <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
            {bill.label}
          </h1>
          <StatusPill tone={status.attention ? "brand" : "muted"}>
            {status.attention ? "Running low" : "All good"}
          </StatusPill>
        </div>
        <p className="m-0 flex flex-wrap gap-x-2.5 gap-y-1.5 text-xs text-muted">
          <span>{kindLabel(bill.kind)}</span>
          <span aria-hidden="true">·</span>
          <span>{bill.provider}</span>
          <span aria-hidden="true">·</span>
          <span className="tabular">{maskReference(bill.reference)}</span>
          {firstPaid ? (
            <>
              <span aria-hidden="true">·</span>
              <span>Paying since {formatLongDate(firstPaid)}</span>
            </>
          ) : null}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {isPayable(bill) ? (
          <Link
            to="/pay"
            search={{ bill: bill.id }}
            className={cn(buttonVariants(), "hover:text-white")}
          >
            {bill.plan_price_ngn ? "Renew" : "Top up"}
          </Link>
        ) : null}
        <Button
          variant="secondary"
          aria-expanded={editing !== null}
          onClick={() => setEditing(editing ? null : "menu")}
        >
          Edit
        </Button>
      </div>

      {editing === "menu" ? (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setEditing("rename")}>
            Rename
          </Button>
          {bill.plan ? (
            <Button variant="secondary" onClick={() => setEditing("plan")}>
              Change plan
            </Button>
          ) : null}
          <Button variant="secondary" onClick={() => setEditing("remove")}>
            Remove bill
          </Button>
        </div>
      ) : null}
      {editing === "rename" ? <Rename bill={bill} onDone={() => setEditing(null)} /> : null}
      {editing === "plan" ? <ChangePlan bill={bill} onDone={() => setEditing(null)} /> : null}
      {editing === "remove" ? <Remove bill={bill} onCancel={() => setEditing(null)} /> : null}

      <nav aria-label="Sections" className="flex flex-wrap gap-2">
        <span aria-current="page" className={pillTabClass(true)}>
          Overview
        </span>
        <Link
          to="/activity"
          search={{ bill: bill.id }}
          className={cn(pillTabClass(false), "hover:text-fg")}
        >
          History
        </Link>
        <Link to="/settings" className={cn(pillTabClass(false), "hover:text-fg")}>
          Limits
        </Link>
      </nav>

      <Overview
        bill={bill}
        history={history}
        isMeter={meterBill(state)?.id === bill.id}
        daysLeft={state.days_left}
      />

      <TopUpChart history={history} />

      {bill.kind === "electricity" ? <RecentTokens history={history} /> : null}
    </>
  );
}

function Overview({
  bill,
  history,
  isMeter,
  daysLeft,
}: {
  bill: Bill;
  history: Receipt[];
  isMeter: boolean;
  daysLeft: number | null;
}) {
  const paid = history.filter((r) => r.status === "delivered");
  const monthAgo = Date.now() - 30 * 24 * 3600 * 1000;
  const lastMonth = paid
    .filter((r) => new Date(r.created_at).getTime() > monthAgo)
    .reduce((sum, r) => sum + r.amount_ngn, 0);

  return (
    <Card>
      {isMeter && daysLeft !== null ? (
        <>
          <Eyebrow>Light left</Eyebrow>
          <div className="flex flex-wrap items-baseline gap-2.5">
            <span className="font-serif text-5xl leading-none">About {daysLeft} days</span>
            <span className="text-xs text-muted">estimated from your top-ups</span>
          </div>
        </>
      ) : (
        <>
          <Eyebrow>{bill.plan_price_ngn ? "Plan" : "Last paid"}</Eyebrow>
          <div className="flex flex-wrap items-baseline gap-2.5">
            <span className="font-serif text-5xl leading-none">
              {bill.plan_price_ngn
                ? formatNaira(bill.plan_price_ngn)
                : bill.last_amount_ngn
                  ? formatNaira(bill.last_amount_ngn)
                  : "Not yet"}
            </span>
            {bill.last_paid_at ? (
              <span className="text-xs text-muted">on {formatShortDate(bill.last_paid_at)}</span>
            ) : null}
          </div>
        </>
      )}
      <StatGrid>
        <Stat label="Last top-up">
          {bill.last_amount_ngn && bill.last_paid_at
            ? `${formatNaira(bill.last_amount_ngn)} · ${formatShortDate(bill.last_paid_at)}`
            : "None yet"}
        </Stat>
        <Stat label="Last 30 days">{formatNaira(lastMonth)}</Stat>
        {bill.kind === "electricity" && bill.last_units ? (
          <Stat label="Units last bought">{bill.last_units} kWh</Stat>
        ) : null}
        <Stat label="Payments">{paid.length}</Stat>
      </StatGrid>
    </Card>
  );
}

function TopUpChart({ history }: { history: Receipt[] }) {
  const paid = history
    .filter((r) => r.status === "delivered")
    .slice(0, 12)
    .reverse();
  if (paid.length < 2) return null;
  const max = Math.max(...paid.map((r) => r.amount_ngn));
  const first = paid[0]!;
  const last = paid.at(-1)!;
  return (
    <Card>
      <Eyebrow>Top-ups</Eyebrow>
      <div
        role="img"
        aria-label={`${paid.length} top-ups from ${formatShortDate(first.created_at)} to ${formatShortDate(last.created_at)}, the latest ${formatNaira(last.amount_ngn)}`}
        className="flex h-40 items-end gap-2.5"
      >
        {paid.map((r, i) => (
          <div key={r.id} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
            <span className="text-[11px] text-muted">{formatNaira(r.amount_ngn)}</span>
            <span
              className={cn(
                "w-full max-w-9 rounded-t-md rounded-b-[2px]",
                i === paid.length - 1 ? "bg-brand" : "bg-bar",
              )}
              style={{ height: `${Math.max(8, (r.amount_ngn / max) * 80)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="tabular flex justify-between text-[11px] text-muted">
        <span>{formatShortDate(first.created_at)}</span>
        <span>{formatShortDate(last.created_at)}</span>
      </div>
    </Card>
  );
}

function RecentTokens({ history }: { history: Receipt[] }) {
  const withTokens = history.filter((r) => r.status === "delivered" && r.token).slice(0, 3);
  if (!withTokens.length) return null;
  return (
    <>
      <SectionHeading action={withTokens.length}>Recent tokens</SectionHeading>
      <RowList>
        {withTokens.map((r) => (
          <TokenLine
            key={r.id}
            token={r.token!}
            note={`${formatShortDate(r.created_at)} · ${formatNaira(r.amount_ngn)}`}
          />
        ))}
      </RowList>
    </>
  );
}

function Rename({ bill, onDone }: { bill: Bill; onDone: () => void }) {
  const [label, setLabel] = useState(bill.label);
  const update = useUpdateBill(bill.id);
  return (
    <form
      className="m-0 flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate({ label: label.trim() }, { onSuccess: onDone });
      }}
    >
      <label htmlFor="rename" className="sr-only">
        Bill name
      </label>
      <input
        id="rename"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        className={cn(inputClass, "max-w-xs flex-1 py-2")}
      />
      <Button type="submit" disabled={!label.trim() || update.isPending}>
        Save
      </Button>
      <Button variant="ghost" onClick={onDone}>
        Cancel
      </Button>
      {update.error ? (
        <p className="m-0 w-full text-[13px] text-brand-soft">{errorCopy(update.error)}</p>
      ) : null}
    </form>
  );
}

function ChangePlan({ bill, onDone }: { bill: Bill; onDone: () => void }) {
  const kind = bill.kind === "tv" ? "tv" : "data";
  const plans = useQuery(plansQuery(kind, bill.provider));
  const update = useUpdateBill(bill.id);
  return (
    <Card>
      <Eyebrow>Choose a plan</Eyebrow>
      <RadioList label="Plan">
        <div className="flex max-h-80 flex-col gap-2 overflow-y-auto pr-1">
          {plans.data?.map((p, i) => (
            <RadioRow
              // The vendor catalogue repeats some plan codes across services.
              key={`${p.provider}-${p.plan}-${i}`}
              checked={p.plan === bill.plan}
              disabled={update.isPending}
              onSelect={() => update.mutate({ plan: p.plan }, { onSuccess: onDone })}
              title={p.label}
              subtitle={formatNaira(p.price_ngn)}
            />
          ))}
        </div>
      </RadioList>
      {update.error ? (
        <p className="m-0 text-[13px] text-brand-soft">{errorCopy(update.error)}</p>
      ) : null}
      <Button variant="ghost" className="self-start" onClick={onDone}>
        Cancel
      </Button>
    </Card>
  );
}

function Remove({ bill, onCancel }: { bill: Bill; onCancel: () => void }) {
  const remove = useDeleteBill();
  const navigate = useNavigate();
  return (
    <Card className="border-brand-warm/40 bg-brand-wash">
      <span className="font-medium">Remove {bill.label}?</span>
      <p className="m-0 text-[13px] text-fg-2">
        Stark won’t be able to pay it any more. Its history stays in your activity.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={remove.isPending}
          onClick={() => remove.mutate(bill.id, { onSuccess: () => navigate({ to: "/bills" }) })}
        >
          Remove
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Keep it
        </Button>
      </div>
      {remove.error ? (
        <p className="m-0 text-[13px] text-brand-soft">{errorCopy(remove.error)}</p>
      ) : null}
    </Card>
  );
}
