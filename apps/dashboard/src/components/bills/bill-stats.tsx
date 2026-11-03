import type { Bill, Payee } from "@stark/api/types";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { formatNaira, formatShortDate } from "@stark/utils/format";

export function BillStats({ bill, payee }: { bill: Bill; payee: Payee | undefined }) {
  return (
    <StatGrid>
      <Stat label="Last top-up">
        {bill.last_amount_ngn && bill.last_paid_at
          ? `${formatNaira(bill.last_amount_ngn)} · ${formatShortDate(bill.last_paid_at)}`
          : "None yet"}
      </Stat>
      <Stat label="This month">{formatNaira(payee?.paid_this_month_ngn ?? 0)}</Stat>
      <Stat label="All time">{formatNaira(payee?.paid_total_ngn ?? 0)}</Stat>
      {bill.kind === "electricity" && bill.last_units ? (
        <Stat label="Units last bought">{bill.last_units} kWh</Stat>
      ) : null}
      <Stat label="Payments">{payee?.payments ?? 0}</Stat>
    </StatGrid>
  );
}
