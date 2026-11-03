import { invalidateMoney } from "@stark/api/mutations";
import { depositQuery } from "@stark/api/queries";
import type { DepositStatus as Status } from "@stark/api/types";
import { buttonVariants } from "@stark/ui/components/button";
import { Notice } from "@stark/ui/components/notice";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { CryptoPayInstructions } from "@/components/wallet/crypto-pay-instructions";

const WAITING: Record<Extract<Status, "open" | "confirming">, string> = {
  open: "Waiting for your payment. This page updates by itself.",
  confirming: "Payment received. Confirming it now.",
};

/** One deposit, polled until it settles. The balance only moves once it reads `credited`. */
export function DepositStatus({ depositId }: { depositId: string }) {
  const qc = useQueryClient();
  const { data: deposit } = useQuery(depositQuery(depositId));

  useEffect(() => {
    if (deposit?.status === "credited") invalidateMoney(qc);
  }, [deposit?.status, qc]);

  if (!deposit) return <Spinner />;

  switch (deposit.status) {
    case "credited":
      return (
        <Notice title={`${formatNaira(deposit.credited_ngn ?? deposit.amount_ngn)} added`}>
          It’s in your balance now.
        </Notice>
      );
    case "expired":
      return (
        <Notice tone="muted" title="This payment window closed">
          Nothing was taken. Start a new one to add money.
        </Notice>
      );
    case "failed":
    case "refunded":
      return (
        <Notice tone="muted" title="That payment didn’t go through">
          {deposit.status === "refunded"
            ? "What you sent is being returned. Nothing was added."
            : "Nothing was added to your balance."}
        </Notice>
      );
    case "open":
    case "confirming":
      return (
        <div className="flex flex-col gap-4">
          {deposit.method === "bank" ? (
            // A new tab, so this page stays open and polls the deposit: it reads
            // `credited` straight from Bachs, with no need for the checkout's redirect
            // (which Bachs refuses to send to localhost) or the webhook.
            <a
              href={deposit.pay.checkout_url}
              target="_blank"
              rel="noopener"
              className={buttonVariants({ size: "lg", block: true })}
            >
              Continue to payment
            </a>
          ) : (
            <CryptoPayInstructions pay={deposit.pay} />
          )}
          <span className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <Spinner />
            {WAITING[deposit.status]}
          </span>
        </div>
      );
  }
}
