import { ActivityRow } from "@/components/activity/activity-row";
import type { Receipt } from "@stark/api";
import { RowList } from "@stark/ui/components/list-row";
import { SectionHeading } from "@stark/ui/components/section-heading";

export function ActivitySection({
  title,
  receipts,
  selectedId,
}: {
  title: string;
  receipts: Receipt[];
  selectedId: string | undefined;
}) {
  return (
    <>
      <SectionHeading>{title}</SectionHeading>
      <RowList>
        {receipts.map((r) => (
          <ActivityRow key={r.id} receipt={r} selected={r.id === selectedId} />
        ))}
      </RowList>
    </>
  );
}
