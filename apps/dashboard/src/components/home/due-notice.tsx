import { BillIcon } from "@/components/bills/bill-icon";
import { DuePayButton } from "@/components/home/due-pay-button";
import { Bills } from "@/lib/bills/bills";
import { Renewals } from "@/lib/renewals/renewals";
import type { DueBill } from "@stark/api";
import { Notice } from "@stark/ui/components/notice";

export function DueNotice({ due }: { due: DueBill }) {
  return (
    <Notice
      tone={due.days_until <= 0 ? "brand" : "muted"}
      icon={<BillIcon bill={due} />}
      title={Renewals.title(due)}
      actions={Bills.isPayable(due) ? <DuePayButton due={due} /> : null}
    >
      {Renewals.detail(due)}
    </Notice>
  );
}
