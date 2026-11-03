import type { Deposit } from "@stark/api/types";
import { Card } from "@stark/ui/components/card";
import { CopyButton } from "@stark/ui/components/copy-button";
import { Eyebrow } from "@stark/ui/components/eyebrow";

type CryptoPay = Extract<Deposit, { method: "crypto" }>["pay"];

/** Exactly what to send, where. A wrong amount or a missing memo is refunded, not credited. */
export function CryptoPayInstructions({ pay }: { pay: CryptoPay }) {
  return (
    <Card className="gap-4">
      <div className="flex flex-col gap-1">
        <Eyebrow>Send exactly</Eyebrow>
        <span className="text-2xl font-medium tabular-nums">
          {pay.amount} {pay.asset}
        </span>
        <span className="text-xs text-muted-foreground">On the {pay.chain} network only.</span>
      </div>
      <div className="flex flex-col gap-2">
        <Eyebrow>To</Eyebrow>
        <code className="break-all rounded-lg bg-surface px-3 py-2 text-[13px]">{pay.address}</code>
        <CopyButton value={pay.address} label="Copy address" />
      </div>
      {pay.memo ? (
        <div className="flex flex-col gap-2">
          <Eyebrow>With this memo</Eyebrow>
          <code className="break-all rounded-lg bg-surface px-3 py-2 text-[13px]">{pay.memo}</code>
          <CopyButton value={pay.memo} label="Copy memo" />
        </div>
      ) : null}
    </Card>
  );
}
