import type { Bill, State } from "@stark/api";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { listRowClass, RowText } from "@stark/ui/components/list-row";
import { cn } from "@stark/ui/utils/cn";
import { Link } from "@tanstack/react-router";
import { billStatus, billSubtitle, kindIcon } from "@/lib/bills";

export function BillIcon({ bill, size = 16 }: { bill: Pick<Bill, "kind">; size?: number }) {
  const Icon = Icons[kindIcon(bill.kind)];
  return (
    <IconTile>
      <Icon size={size} />
    </IconTile>
  );
}

export function BillRow({ bill, state }: { bill: Bill; state: State }) {
  const status = billStatus(bill, state);
  return (
    <Link to="/bills/$billId" params={{ billId: bill.id }} className={listRowClass}>
      <BillIcon bill={bill} />
      <RowText title={bill.label} subtitle={billSubtitle(bill)} />
      <span className={cn("text-xs", status.attention ? "text-brand-warm" : "text-fg-2")}>
        {status.text}
      </span>
      <Icons.ChevronRight size={16} className="text-muted-foreground" />
    </Link>
  );
}
