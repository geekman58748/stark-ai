import type { PaymentRequest } from "@stark/api/types";
import { formatNaira } from "@stark/utils/format";
import { Approvals } from "@/lib/approvals/approvals";

export function ApprovalSummary({ request }: { request: PaymentRequest }) {
  return (
    <>
      <div className="flex flex-col gap-0.5">
        <span className="text-[13px] text-fg-2">Stark wants to pay</span>
        <span className="font-serif text-[28px] leading-tight font-medium">
          {formatNaira(request.amount_ngn)}
        </span>
        <span className="text-[14px]">to {request.bill_label}</span>
      </div>
      <p className="m-0 text-[13px] text-fg-2">
        {Approvals.reason(request)}, so it asked first. Approving pays this one amount. Your limits
        stay the same. {Approvals.timeLeft(request)}.
      </p>
    </>
  );
}
