import type { Bill, Receipt } from "@stark/api";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { formatNaira, formatShortDate } from "@stark/utils/format";

export function BillStats({ bill, history }: { bill: Bill; history: Receipt[] }) {
  const paid = history.filter((r) => r.status === "delivered");
  const monthAgo = Date.now() - 30 * 24 * 3600 * 1000;
  const lastMonth = paid
    .filter((r) => new Date(r.created_at).getTime() > monthAgo)
    .reduce((sum, r) => sum + r.amount_ngn, 0);

  return (
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
  );
}
