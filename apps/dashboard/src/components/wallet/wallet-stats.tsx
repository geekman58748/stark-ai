import type { Wallet } from "@stark/api";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { formatNaira } from "@stark/utils/format";

export function WalletStats({ wallet }: { wallet: Wallet }) {
  return (
    <StatGrid>
      <Stat label="Added this month">{formatNaira(wallet.added_this_month_ngn)}</Stat>
      <Stat label="Spent this month">{formatNaira(wallet.spent_ngn)}</Stat>
      <Stat label="Monthly limit left">{formatNaira(wallet.remaining_cap_ngn)}</Stat>
      <Stat label="Pays from">This wallet</Stat>
    </StatGrid>
  );
}
