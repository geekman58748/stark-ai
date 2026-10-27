import { BillRow } from "@/components/bills/bill-row";
import { EmptyBills } from "@/components/home/empty-bills";
import { SeeAllLink } from "@/components/home/see-all-link";
import type { State } from "@stark/api";
import { RowList } from "@stark/ui/components/list-row";
import { SectionHeading } from "@stark/ui/components/section-heading";

export function HomeBills({ state }: { state: State }) {
  return (
    <>
      <SectionHeading action={<SeeAllLink to="/bills" />}>
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
    </>
  );
}
