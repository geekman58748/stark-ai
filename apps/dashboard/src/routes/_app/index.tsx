import { AskStark } from "@/components/home/ask-stark";
import { BalanceCard } from "@/components/home/balance-card";
import { DueNotice } from "@/components/home/due-notice";
import { HomeBills } from "@/components/home/home-bills";
import { HomeHeader } from "@/components/home/home-header";
import { LowMeterNotice } from "@/components/home/low-meter-notice";
import { NoticedCard } from "@/components/home/noticed-card";
import { RecentActivity } from "@/components/home/recent-activity";
import { Bills } from "@/lib/bills/bills";
import { Renewals } from "@/lib/renewals/renewals";
import { activityQuery, stateQuery, suggestionsQuery } from "@stark/api";
import { noop, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_app/")({
  loader: ({ context }) => {
    void context.queryClient.query(activityQuery()).catch(noop);
  },
  head: () => ({ meta: [{ title: "Home · Stark" }] }),
  component: Home,
});

function Home() {
  const { data: state } = useSuspenseQuery(stateQuery());
  const { data: activity } = useQuery(activityQuery());
  const { data: suggestions } = useQuery(suggestionsQuery());
  const meter = Bills.meter(state);
  const low =
    meter && state.days_left !== null && state.days_left <= Bills.LOW_DAYS;
  // Reminders the server already judged due (state.due_soon): the soonest one gets
  // its own action strip, the rest stay in "Stark noticed" as finished sentences.
  const due = Renewals.next(state.due_soon);
  // The meter Notice and the renewal Notice own their warnings; suggestions say the rest.
  const noticed = (suggestions ?? []).filter(
    (sug) =>
      !(low && sug.reason.startsWith("units_low")) &&
      sug.id !== `sug_due_${due?.id}`,
  );
  const needing = Number(Boolean(low)) + Number(Boolean(due));

  return (
    <>
      <HomeHeader firstName={state.first_name} needing={needing} />
      <BalanceCard state={state} meter={meter} />
      {due ? <DueNotice due={due} /> : null}
      {low && meter ? (
        <LowMeterNotice meter={meter} daysLeft={state.days_left} />
      ) : null}
      {noticed.length ? <NoticedCard suggestions={noticed} /> : null}
      <AskStark />
      <HomeBills state={state} />
      <RecentActivity activity={activity} />
    </>
  );
}
