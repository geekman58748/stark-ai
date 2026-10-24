import { activityQuery, stateQuery, suggestionsQuery } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
} from "@stark/ui/components/empty";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@stark/ui/components/input-group";
import { RowList } from "@stark/ui/components/list-row";
import { Notice } from "@stark/ui/components/notice";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { StatusPill } from "@stark/ui/components/status-pill";
import { cn } from "@stark/ui/utils/cn";
import { formatNaira, greeting } from "@stark/utils/format";
import { noop, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ActivityRow } from "@/components/activity-row";
import { BillIcon, BillRow } from "@/components/bill-row";
import { isPayable, LOW_DAYS, meterBill } from "@/lib/bills";
import { nextRenewal, renewalDetail, renewalTitle } from "@/lib/renewals";

export const Route = createFileRoute("/_app/")({
  loader: ({ context }) => {
    void context.queryClient.query(activityQuery()).catch(noop);
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
  const { data: suggestions } = useQuery(suggestionsQuery());
  const meter = meterBill(state);
  const low = meter && state.days_left !== null && state.days_left <= LOW_DAYS;
  // Reminders the server already judged due (state.due_soon): the soonest one gets
  // its own action strip, the rest stay in "Stark noticed" as finished sentences.
  const due = nextRenewal(state.due_soon);
  // The meter Notice and the renewal Notice own their warnings; suggestions say the rest.
  const noticed = (suggestions ?? []).filter(
    (sug) => !(low && sug.reason.startsWith("units_low")) && sug.id !== `sug_due_${due?.id}`,
  );
  const needing = Number(Boolean(low)) + Number(Boolean(due));
  const headline =
    needing === 0
      ? "Everything’s covered"
      : needing === 1
        ? "One thing needs you"
        : "Two things need you";

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <span className="text-[13px] text-muted-foreground">
          {greeting()}, {state.first_name}
        </span>
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
            {headline}
          </h1>
          <StatusPill>Stark is on</StatusPill>
        </div>
      </div>

      <Card>
        <Eyebrow>Balance</Eyebrow>
        <div className="flex flex-wrap items-baseline gap-2.5">
          <span className="font-serif text-5xl leading-none">{formatNaira(state.balance_ngn)}</span>
          <span className="text-xs text-muted-foreground">
            {runway(state.balance_ngn, state.spent_ngn)}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button nativeButton={false} render={<Link to="/wallet/add" />}>
            Add money
          </Button>
          <Button variant="secondary" nativeButton={false} render={<Link to="/wallet" />}>
            Withdraw
          </Button>
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

      {due ? (
        <Notice
          tone={due.days_until <= 0 ? "brand" : "muted"}
          icon={<BillIcon bill={due} />}
          title={renewalTitle(due)}
          actions={
            isPayable(due) ? (
              <Button
                nativeButton={false}
                render={
                  <Link to="/pay" search={{ bill: due.id, amount: due.price_ngn ?? undefined }} />
                }
              >
                Pay{due.price_ngn ? ` ${formatNaira(due.price_ngn)}` : " it"}
              </Button>
            ) : null
          }
        >
          {renewalDetail(due)}
        </Notice>
      ) : null}

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
              <Button
                nativeButton={false}
                render={
                  <Link
                    to="/pay"
                    search={{ bill: meter.id, amount: meter.last_amount_ngn ?? undefined }}
                  />
                }
              >
                Top up {meter.last_amount_ngn ? formatNaira(meter.last_amount_ngn) : ""}
              </Button>
              <Button variant="secondary" nativeButton={false} render={<Link to="/bills" />}>
                Later
              </Button>
            </>
          }
        >
          About {state.days_left} days left at your usual use.
        </Notice>
      ) : null}

      {noticed.length ? (
        <Card className="gap-2.5">
          <Eyebrow>Stark noticed</Eyebrow>
          {noticed.map((sug) => (
            <div key={sug.id} className="flex items-start gap-2.5">
              <span
                aria-hidden="true"
                className={cn(
                  "mt-1.5 size-1.5 shrink-0 rounded-full",
                  sug.severity === "alert"
                    ? "bg-destructive"
                    : sug.severity === "warn"
                      ? "bg-brand-warm"
                      : "bg-faint",
                )}
              />
              <span className="text-sm leading-relaxed">{sug.text}</span>
            </div>
          ))}
        </Card>
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
      className="m-0"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) navigate({ to: "/talk", search: { q: text.trim() } });
      }}
    >
      <InputGroup className="h-auto rounded-full border-white/10 bg-surface py-1.5 pr-1.5 pl-4.5 dark:bg-surface">
        <InputGroupInput
          aria-label="Ask Stark"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask Stark: “buy 2GB for my line”"
          className="h-auto px-0 py-2 text-[15px]"
        />
        <InputGroupAddon align="inline-end" className="py-0">
          {text.trim() ? (
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              aria-label="Send"
              className="size-10 rounded-full"
            >
              <Icons.ArrowRight className="size-4.5" />
            </InputGroupButton>
          ) : (
            <InputGroupButton
              variant="default"
              size="icon-sm"
              aria-label="Speak instead"
              nativeButton={false}
              render={<Link to="/talk" />}
              className="size-10 rounded-full"
            >
              <Icons.Mic className="size-4.5" />
            </InputGroupButton>
          )}
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}

function EmptyBills() {
  return (
    <Empty className="rounded-row border border-dashed border-white/12 p-6">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icons.Bills size={16} />
        </EmptyMedia>
        <EmptyDescription>Add a bill and Stark starts watching it for you.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="secondary" nativeButton={false} render={<Link to="/bills/new" />}>
          <Icons.Add size={16} />
          Add your first bill
        </Button>
      </EmptyContent>
    </Empty>
  );
}
