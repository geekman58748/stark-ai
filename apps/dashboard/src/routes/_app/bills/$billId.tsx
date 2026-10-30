import { activityQuery, billQuery, stateQuery } from "@stark/api";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { BillActions } from "@/components/bills/bill-actions";
import type { BillEdit } from "@/components/bills/bill-edit-menu";
import { BillHeader } from "@/components/bills/bill-header";
import { BillOverview } from "@/components/bills/bill-overview";
import { BillSectionsNav } from "@/components/bills/bill-sections-nav";
import { ChangePlanDialog } from "@/components/bills/change-plan-dialog";
import { RecentTokens } from "@/components/bills/recent-tokens";
import { RemoveBillDialog } from "@/components/bills/remove-bill-dialog";
import { RenameBillDialog } from "@/components/bills/rename-bill-dialog";
import { TopUpChart } from "@/components/bills/top-up-chart";
import { BackLink } from "@/components/shell/back-link";
import { Bills } from "@/lib/bills/bills";

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
  const [editing, setEditing] = useState<BillEdit | null>(null);

  const history = activity.filter((r) => r.bill_id === bill.id);
  const status = Bills.status(bill, state);
  const firstPaid = history.at(-1)?.created_at;

  return (
    <>
      <BackLink to="/bills">Bills</BackLink>
      <BillHeader bill={bill} attention={status.attention} firstPaid={firstPaid} />
      <BillActions bill={bill} onEdit={setEditing} />

      <RenameBillDialog bill={bill} open={editing === "rename"} onClose={() => setEditing(null)} />
      {bill.plan ? (
        <ChangePlanDialog
          bill={bill}
          plan={bill.plan}
          open={editing === "plan"}
          onClose={() => setEditing(null)}
        />
      ) : null}
      <RemoveBillDialog bill={bill} open={editing === "remove"} onCancel={() => setEditing(null)} />

      <BillSectionsNav bill={bill} />

      <BillOverview
        bill={bill}
        history={history}
        isMeter={Bills.meter(state)?.id === bill.id}
        daysLeft={state.days_left}
      />

      <TopUpChart history={history} />

      {bill.kind === "electricity" ? <RecentTokens history={history} /> : null}
    </>
  );
}
