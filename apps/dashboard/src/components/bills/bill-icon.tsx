import type { Bill } from "@stark/api";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { BillKinds } from "@/lib/bills/bill-kinds";

export function BillIcon({ bill, size = 16 }: { bill: Pick<Bill, "kind">; size?: number }) {
  const Icon = Icons[BillKinds.icon(bill.kind)];
  return (
    <IconTile>
      <Icon size={size} />
    </IconTile>
  );
}
