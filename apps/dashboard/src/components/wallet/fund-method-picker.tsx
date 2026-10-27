import { type FundMethod, FundMethods } from "@/lib/wallet/fund-methods";
import { RadioList, RadioRow } from "@stark/ui/components/radio-row";

export function FundMethodPicker({
  value,
  onValueChange,
}: {
  value: FundMethod;
  onValueChange: (method: FundMethod) => void;
}) {
  return (
    <RadioList label="How to pay" value={value} onValueChange={onValueChange}>
      {FundMethods.all.map((m) => (
        <RadioRow key={m.id} value={m.id} title={m.name} subtitle={m.note} />
      ))}
    </RadioList>
  );
}
