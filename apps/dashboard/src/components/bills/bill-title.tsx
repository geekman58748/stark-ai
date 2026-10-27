import { BillIcon } from "@/components/bills/bill-icon";
import type { Bill } from "@stark/api";
import { StatusPill } from "@stark/ui/components/status-pill";

export function BillTitle({
  bill,
  attention,
}: {
  bill: Bill;
  attention: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <BillIcon bill={bill} />
      <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
        {bill.label}
      </h1>
      <StatusPill tone={attention ? "brand" : "muted"}>
        {attention ? "Running low" : "All good"}
      </StatusPill>
    </div>
  );
}
