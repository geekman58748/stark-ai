import type { Bill, Payee } from "@stark/api/types";
import { Card } from "@stark/ui/components/card";
import { BillStats } from "@/components/bills/bill-stats";
import { MeterHeadline } from "@/components/bills/meter-headline";
import { PaymentHeadline } from "@/components/bills/payment-headline";

export function BillOverview({
  bill,
  payee,
  isMeter,
  daysLeft,
}: {
  bill: Bill;
  payee: Payee | undefined;
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
      <BillStats bill={bill} payee={payee} />
    </Card>
  );
}
