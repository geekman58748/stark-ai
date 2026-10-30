import type { Bill, State } from "@stark/api";
import { RowList } from "@stark/ui/components/list-row";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { BillRow } from "@/components/bills/bill-row";

export function BillGroup({ title, bills, state }: { title: string; bills: Bill[]; state: State }) {
  return (
    <>
      <SectionHeading action={bills.length}>{title}</SectionHeading>
      <RowList>
        {bills.map((b) => (
          <BillRow key={b.id} bill={b} state={state} />
        ))}
      </RowList>
    </>
  );
}
