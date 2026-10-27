import { ActivityRow } from "@/components/activity/activity-row";
import type { Receipt } from "@stark/api";
import { Empty, EmptyDescription } from "@stark/ui/components/empty";
import { RowList } from "@stark/ui/components/list-row";

export function MoneyMoves({ moves }: { moves: Receipt[] }) {
  return (
    <RowList>
      {moves.map((r) => (
        <ActivityRow key={r.id} receipt={r} />
      ))}
      {!moves.length ? (
        <Empty className="rounded-row border border-dashed border-white/12 p-6">
          <EmptyDescription>No money in or out yet.</EmptyDescription>
        </Empty>
      ) : null}
    </RowList>
  );
}
