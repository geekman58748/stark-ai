import { BillKinds } from "@/lib/bills/bill-kinds";
import type { Bill } from "@stark/api";
import { formatLongDate, maskReference } from "@stark/utils/format";

export function BillFacts({
  bill,
  firstPaid,
}: {
  bill: Bill;
  firstPaid: string | undefined;
}) {
  return (
    <p className="m-0 flex flex-wrap gap-x-2.5 gap-y-1.5 text-xs text-muted-foreground">
      <span>{BillKinds.label(bill.kind)}</span>
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
  );
}
