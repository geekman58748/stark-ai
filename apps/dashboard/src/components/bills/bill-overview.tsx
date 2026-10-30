import type { Bill, Receipt } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { BillStats } from "@/components/bills/bill-stats";
import { MeterHeadline } from "@/components/bills/meter-headline";
import { PaymentHeadline } from "@/components/bills/payment-headline";

export function BillOverview({
  bill,
  history,
  isMeter,
  daysLeft,
}: {
  bill: Bill;
  history: Receipt[];
  isMeter: boolean;
  daysLeft: number | null;
}) {
  return (
    <Card>
      {isMeter && daysLeft !== null ? (
        <MeterHeadline daysLeft={daysLeft} />
      ) : (
        <PaymentHeadline bill={bill} />
      )}
      <BillStats bill={bill} history={history} />
    </Card>
  );
}
