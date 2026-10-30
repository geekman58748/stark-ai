import type { Bill, State } from "@stark/api";
import { RadioList, RadioRow } from "@stark/ui/components/radio-row";
import { BillKinds } from "@/lib/bills/bill-kinds";
import { Bills } from "@/lib/bills/bills";

export function BillPicker({
  bills,
  state,
  value,
  onValueChange,
}: {
  bills: Bill[];
  state: State;
  value: string | undefined;
  onValueChange: (id: string) => void;
}) {
  return (
    <RadioList label="Which bill" value={value} onValueChange={onValueChange}>
      {bills.map((b) => (
        <RadioRow
          key={b.id}
          value={b.id}
          title={b.label}
          subtitle={`${BillKinds.label(b.kind)} · ${Bills.status(b, state).text}`}
        />
      ))}
    </RadioList>
  );
}
