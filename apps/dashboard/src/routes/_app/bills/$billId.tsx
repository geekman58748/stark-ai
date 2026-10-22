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
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@stark/ui/components/alert-dialog";
import { Button } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@stark/ui/components/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@stark/ui/components/dropdown-menu";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { Field, FieldError, FieldLabel } from "@stark/ui/components/field";
import { Icons } from "@stark/ui/components/icons";
import { Input } from "@stark/ui/components/input";
import { RowList } from "@stark/ui/components/list-row";
import { pillTabClass } from "@stark/ui/components/pill-tabs";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { Spinner } from "@stark/ui/components/spinner";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { StatusPill } from "@stark/ui/components/status-pill";
import { cn } from "@stark/ui/utils/cn";
import { formatLongDate, formatNaira, formatShortDate, maskReference } from "@stark/utils/format";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";
import { BackLink } from "@/components/app-shell";
import { BillIcon } from "@/components/bill-row";
import { PlanSelect } from "@/components/plan-select";
import { TokenLine } from "@/components/token-card";
import { billStatus, isPayable, kindLabel, meterBill } from "@/lib/bills";

export const Route = createFileRoute("/_app/bills/$billId")({
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.query({
        ...billQuery(params.billId),
        staleTime: "static",
      }),
      context.queryClient.query({ ...activityQuery(), staleTime: "static" }),
    ]),
  head: () => ({ meta: [{ title: "Bill · Stark" }] }),
  component: BillDetail,
});

function BillDetail() {
  const { billId } = Route.useParams();
  const { data: bill } = useSuspenseQuery(billQuery(billId));
  const { data: state } = useSuspenseQuery(stateQuery());
  const { data: activity } = useSuspenseQuery(activityQuery());
  const [editing, setEditing] = useState<"rename" | "plan" | "remove" | null>(null);

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
        <p className="m-0 flex flex-wrap gap-x-2.5 gap-y-1.5 text-xs text-muted-foreground">
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
          <Button nativeButton={false} render={<Link to="/pay" search={{ bill: bill.id }} />}>
            {bill.plan_price_ngn ? "Renew" : "Top up"}
          </Button>
        ) : null}
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="secondary" />}>
            Edit
            <Icons.ChevronDown size={14} />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-44">
            <DropdownMenuItem onClick={() => setEditing("rename")}>Rename</DropdownMenuItem>
            {bill.plan ? (
              <DropdownMenuItem onClick={() => setEditing("plan")}>Change plan</DropdownMenuItem>
            ) : null}
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={() => setEditing("remove")}>
              Remove bill
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Dialog open={editing === "rename"} onOpenChange={(open) => open || setEditing(null)}>
        <DialogContent>
          <Rename bill={bill} onDone={() => setEditing(null)} />
        </DialogContent>
      </Dialog>
      {bill.plan ? (
        <Dialog open={editing === "plan"} onOpenChange={(open) => open || setEditing(null)}>
          <DialogContent>
            <ChangePlan bill={bill} plan={bill.plan} onDone={() => setEditing(null)} />
          </DialogContent>
        </Dialog>
      ) : null}
      <Remove bill={bill} open={editing === "remove"} onCancel={() => setEditing(null)} />

      <nav aria-label="Sections" className="flex flex-wrap gap-2">
        <span aria-current="page" className={pillTabClass(true)}>
          Overview
        </span>
        <Link to="/activity" search={{ bill: bill.id }} className={pillTabClass(false)}>
          History
        </Link>
        <Link to="/settings" className={pillTabClass(false)}>
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
            <span className="text-xs text-muted-foreground">estimated from your top-ups</span>
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
              <span className="text-xs text-muted-foreground">
                on {formatShortDate(bill.last_paid_at)}
              </span>
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
            <span className="text-[11px] text-muted-foreground">{formatNaira(r.amount_ngn)}</span>
            <span
              className={cn(
                "w-full max-w-9 rounded-t-md rounded-b-xs",
                i === paid.length - 1 ? "bg-brand" : "bg-bar",
              )}
              style={{ height: `${Math.max(8, (r.amount_ngn / max) * 80)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="tabular flex justify-between text-[11px] text-muted-foreground">
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
  const id = useId();
  return (
    <form
      className="m-0 grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate({ label: label.trim() }, { onSuccess: onDone });
      }}
    >
      <DialogHeader>
        <DialogTitle>Rename bill</DialogTitle>
        <DialogDescription>This is the name Stark uses when it talks about it.</DialogDescription>
      </DialogHeader>
      <Field>
        <FieldLabel htmlFor={id} className="font-normal text-fg-2">
          Bill name
        </FieldLabel>
        <Input id={id} value={label} onChange={(e) => setLabel(e.target.value)} autoFocus />
        {update.error ? <FieldError>{errorCopy(update.error)}</FieldError> : null}
      </Field>
      <DialogFooter>
        <DialogClose render={<Button variant="ghost" />}>Cancel</DialogClose>
        <Button type="submit" disabled={!label.trim() || update.isPending}>
          {update.isPending ? <Spinner /> : null}
          Save
        </Button>
      </DialogFooter>
    </form>
  );
}

function ChangePlan({ bill, plan, onDone }: { bill: Bill; plan: string; onDone: () => void }) {
  const plans = useQuery(plansQuery(bill.kind === "tv" ? "tv" : "data", bill.provider));
  const [picked, setPicked] = useState(plan);
  const update = useUpdateBill(bill.id);
  const id = useId();
  return (
    <form
      className="m-0 grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate({ plan: picked }, { onSuccess: onDone });
      }}
    >
      <DialogHeader>
        <DialogTitle>Change plan</DialogTitle>
        <DialogDescription>
          Stark buys this plan from {bill.provider} each time {bill.label} renews.
        </DialogDescription>
      </DialogHeader>
      <Field>
        <FieldLabel htmlFor={id} className="font-normal text-fg-2">
          Plan
        </FieldLabel>
        <PlanSelect
          id={id}
          plans={plans.data}
          provider={bill.provider}
          value={picked}
          onChange={setPicked}
          disabled={update.isPending}
        />
        {update.error ? <FieldError>{errorCopy(update.error)}</FieldError> : null}
      </Field>
      <DialogFooter>
        <DialogClose render={<Button variant="ghost" />}>Cancel</DialogClose>
        <Button type="submit" disabled={picked === plan || update.isPending}>
          {update.isPending ? <Spinner /> : null}
          Save plan
        </Button>
      </DialogFooter>
    </form>
  );
}

function Remove({ bill, open, onCancel }: { bill: Bill; open: boolean; onCancel: () => void }) {
  const remove = useDeleteBill();
  const navigate = useNavigate();
  return (
    <AlertDialog open={open} onOpenChange={(next) => next || onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove {bill.label}?</AlertDialogTitle>
          <AlertDialogDescription>
            Stark won’t be able to pay it any more. Its history stays in your activity.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {remove.error ? <FieldError>{errorCopy(remove.error)}</FieldError> : null}
        <AlertDialogFooter>
          <AlertDialogCancel variant="secondary">Keep it</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() => remove.mutate(bill.id, { onSuccess: () => navigate({ to: "/bills" }) })}
          >
            {remove.isPending ? <Spinner /> : null}
            Remove
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
