import type { Bill } from "@stark/api";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { formatNaira, formatShortDate } from "@stark/utils/format";

export function PaymentHeadline({ bill }: { bill: Bill }) {
  return (
    <>
      <Eyebrow>{bill.plan_price_ngn ? "Plan" : "Last paid"}</Eyebrow>
      <div className="flex flex-wrap items-baseline gap-2.5">
        <span className="font-serif text-5xl leading-none">
          {bill.plan_price_ngn
            ? formatNaira(bill.plan_price_ngn)
            : bill.last_amount_ngn
              ? formatNaira(bill.last_amount_ngn)
              : "Not yet"}
        </span>
        {bill.last_paid_at ? (
          <span className="text-xs text-muted-foreground">
            on {formatShortDate(bill.last_paid_at)}
          </span>
        ) : null}
      </div>
    </>
  );
}
