import type { BillKind } from "@stark/api";
import { ChipGroup, ChoiceChip } from "@stark/ui/components/choice-chip";
import { BillKinds } from "@/lib/bills/bill-kinds";

export function BillKindChips({
  kind,
  onPick,
}: {
  kind: BillKind;
  onPick: (kind: BillKind) => void;
}) {
  return (
    <ChipGroup label="Bill type" columns={3}>
      {BillKinds.all.map((k) => (
        <ChoiceChip
          key={k.kind}
          selected={k.kind === kind}
          onClick={() => onPick(k.kind)}
          className="text-sm"
        >
          {k.label}
        </ChoiceChip>
      ))}
    </ChipGroup>
  );
}
