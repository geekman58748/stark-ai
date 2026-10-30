import type { State } from "@stark/api";
import { formatNaira } from "@stark/utils/format";
import { RenewalCard } from "@/components/talk/renewal-card";
import { StatusCard } from "@/components/talk/status-card";
import { Bills } from "@/lib/bills/bills";
import { Renewals } from "@/lib/renewals/renewals";

export function StatusCards({ state }: { state: State }) {
  const meter = Bills.meter(state);
  const due = Renewals.next(state.due_soon);

  return (
    <section aria-label="Status" className="order-first grid grid-cols-2 gap-2 lg:order-0">
      {meter && state.days_left !== null ? (
        <StatusCard label={`${meter.label} meter`}>~{state.days_left} days</StatusCard>
      ) : null}
      <StatusCard label="Limit left">{formatNaira(state.remaining_cap_ngn)}</StatusCard>
      {due ? <RenewalCard due={due} /> : null}
    </section>
  );
}
