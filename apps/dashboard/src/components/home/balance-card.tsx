import type { Bill, State } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { BalanceActions } from "@/components/home/balance-actions";
import { HomeStats } from "@/components/home/home-stats";
import { BalanceFigure } from "@/components/wallet/balance-figure";
import { Runway } from "@/lib/wallet/runway";

export function BalanceCard({ state, meter }: { state: State; meter: Bill | undefined }) {
  return (
    <Card>
      <Eyebrow>Balance</Eyebrow>
      <BalanceFigure
        amount={state.balance_ngn}
        note={Runway.note(state.balance_ngn, state.spent_ngn)}
      />
      <BalanceActions />
      <HomeStats state={state} meter={meter} />
    </Card>
  );
}
