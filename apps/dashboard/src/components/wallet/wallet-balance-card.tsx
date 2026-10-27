import { BalanceFigure } from "@/components/wallet/balance-figure";
import { WalletActions } from "@/components/wallet/wallet-actions";
import { WalletStats } from "@/components/wallet/wallet-stats";
import { WithdrawForm } from "@/components/wallet/withdraw-form";
import type { Wallet } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import {
  Collapsible,
  CollapsibleContent,
} from "@stark/ui/components/collapsible";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { useState } from "react";

export function WalletBalanceCard({ wallet }: { wallet: Wallet }) {
  const [withdrawing, setWithdrawing] = useState(false);

  return (
    <Card>
      <Eyebrow>Available</Eyebrow>
      <BalanceFigure amount={wallet.balance_ngn} note="ready for your bills" />
      <Collapsible
        open={withdrawing}
        onOpenChange={setWithdrawing}
        className="flex flex-col gap-3.5"
      >
        <WalletActions />
        <CollapsibleContent>
          <WithdrawForm
            max={wallet.balance_ngn}
            onDone={() => setWithdrawing(false)}
          />
        </CollapsibleContent>
      </Collapsible>
      <WalletStats wallet={wallet} />
    </Card>
  );
}
