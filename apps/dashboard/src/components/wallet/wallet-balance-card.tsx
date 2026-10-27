import { BalanceFigure } from "@/components/wallet/balance-figure";
import { WalletActions } from "@/components/wallet/wallet-actions";
import { WalletStats } from "@/components/wallet/wallet-stats";
import type { Wallet } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";

export function WalletBalanceCard({ wallet }: { wallet: Wallet }) {
  return (
    <Card>
      <Eyebrow>Available</Eyebrow>
      <BalanceFigure amount={wallet.balance_ngn} note="ready for your bills" />
      <WalletActions />
      <WalletStats wallet={wallet} />
    </Card>
  );
}
