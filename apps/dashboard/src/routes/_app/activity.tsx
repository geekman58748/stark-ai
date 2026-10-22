import { ActivityRow } from "@/components/activity-row";
import { PageTitle } from "@/components/app-shell";
import { TokenLine } from "@/components/token-card";
import {
  type ActivityFilter,
  matchesFilter,
  signedAmount,
  statusDisplay,
} from "@/lib/receipts";
import { activityQuery, type Receipt } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { RowList } from "@stark/ui/components/list-row";
import { PillTabs } from "@stark/ui/components/pill-tabs";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { StatusPill } from "@stark/ui/components/status-pill";
import { cn } from "@stark/ui/utils/cn";
import { formatDateTime, formatNaira, isToday } from "@stark/utils/format";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

const filters: { value: ActivityFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "bills", label: "Bills paid" },
  { value: "in", label: "Money in" },
  { value: "declined", label: "Declined" },
];

export const Route = createFileRoute("/_app/activity")({
  validateSearch: z.object({
    filter: z.enum(["all", "bills", "in", "declined"]).optional(),
    receipt: z.string().optional(),
    bill: z.string().optional(),
  }),
  loader: ({ context }) =>
    context.queryClient.query({ ...activityQuery(), staleTime: "static" }),
  head: () => ({ meta: [{ title: "Activity · Stark" }] }),
  component: Activity,
});

function Activity() {
  const { data } = useSuspenseQuery(activityQuery());
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const filter = search.filter ?? "all";

  const rows = data.filter(
    (r) =>
      matchesFilter(r, filter) && (!search.bill || r.bill_id === search.bill),
  );
  const selected = rows.find((r) => r.id === search.receipt) ?? rows[0];
  const today = rows.filter((r) => isToday(r.created_at));
  const earlier = rows.filter((r) => !isToday(r.created_at));

  return (
    <>
      <PageTitle>Activity</PageTitle>
      <PillTabs
        label="Show"
        value={filter}
        tabs={filters}
        onChange={(value) =>
          navigate({
            search: (prev) => ({
              ...prev,
              filter: value === "all" ? undefined : value,
              receipt: undefined,
            }),
          })
        }
      />

      {selected ? <ReceiptCard receipt={selected} /> : null}

      {today.length ? (
        <>
          <SectionHeading>Today</SectionHeading>
          <RowList>
            {today.map((r) => (
              <ActivityRow
                key={r.id}
                receipt={r}
                selected={r.id === selected?.id}
              />
            ))}
          </RowList>
        </>
      ) : null}
      {earlier.length ? (
        <>
          <SectionHeading>Earlier</SectionHeading>
          <RowList>
            {earlier.map((r) => (
              <ActivityRow
                key={r.id}
                receipt={r}
                selected={r.id === selected?.id}
              />
            ))}
          </RowList>
        </>
      ) : null}
      {!rows.length ? (
        <p className="m-0 text-[13px] text-muted-foreground">
          Nothing here yet.
        </p>
      ) : null}
    </>
  );
}

function ReceiptCard({ receipt }: { receipt: Receipt }) {
  const status = statusDisplay(receipt);
  return (
    <Card aria-live="polite">
      <div className="flex items-center gap-2">
        <Eyebrow>Receipt</Eyebrow>
        <StatusPill
          tone={status.tone === "brand" ? "brand" : "muted"}
          className="ml-auto"
        >
          {status.label}
        </StatusPill>
      </div>
      <div className="flex flex-col gap-1">
        <span
          className={cn(
            "font-serif text-5xl leading-none",
            receipt.status === "declined" && "text-muted-foreground",
          )}
        >
          {formatNaira(signedAmount(receipt), {
            sign: receipt.type === "deposit",
          })}
        </span>
        <span className="text-xs text-muted-foreground">
          {receipt.bill_label} · {formatDateTime(receipt.created_at)}
        </span>
      </div>
      {receipt.status === "declined" ? (
        <p className="m-0 text-[13px] text-fg-2">
          Stark stopped this because it broke one of your rules. Nothing was
          charged.
        </p>
      ) : null}
      {receipt.status === "pending" ? (
        <p className="m-0 text-[13px] text-fg-2">
          Still going through at the provider. You haven’t been charged yet.
        </p>
      ) : null}
      {receipt.token && receipt.status === "delivered" ? (
        <TokenLine token={receipt.token} />
      ) : null}
      <StatGrid>
        {receipt.source ? (
          <Stat label="Asked via">{receipt.source}</Stat>
        ) : null}
        {receipt.units ? <Stat label="Units">{receipt.units} kWh</Stat> : null}
        <Stat label="Receipt ID">
          <span className="tabular">{receipt.id.toUpperCase()}</span>
        </Stat>
      </StatGrid>
    </Card>
  );
}
