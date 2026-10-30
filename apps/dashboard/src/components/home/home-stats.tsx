import type { Bill, State } from "@stark/api";
import { Stat, StatGrid } from "@stark/ui/components/stat";
import { formatNaira } from "@stark/utils/format";

export function HomeStats({ state, meter }: { state: State; meter: Bill | undefined }) {
  return (
    <StatGrid>
      <Stat label="Spent this month">
        {formatNaira(state.spent_ngn)} of {formatNaira(state.cap_ngn)}
      </Stat>
      <Stat label="Limit left">{formatNaira(state.remaining_cap_ngn)}</Stat>
      {meter && state.days_left !== null ? (
        <Stat label={meter.label}>About {state.days_left} days left</Stat>
      ) : null}
      <Stat label="Bills">{state.bills.length} active</Stat>
    </StatGrid>
  );
}
