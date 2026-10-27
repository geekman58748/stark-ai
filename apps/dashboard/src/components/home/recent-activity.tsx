import { ActivityRow } from "@/components/activity/activity-row";
import { SeeAllLink } from "@/components/home/see-all-link";
import type { Receipt } from "@stark/api";
import { RowList } from "@stark/ui/components/list-row";
import { SectionHeading } from "@stark/ui/components/section-heading";

export function RecentActivity({
  activity,
}: {
  activity: Receipt[] | undefined;
}) {
  return (
    <>
      <SectionHeading action={<SeeAllLink to="/activity" />}>
        Recent activity
      </SectionHeading>
      <RowList>
        {activity?.slice(0, 3).map((r) => (
          <ActivityRow key={r.id} receipt={r} />
        ))}
      </RowList>
    </>
  );
}
