import { limitsQuery } from "@stark/api";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AccountCard } from "@/components/settings/account-card";
import { ListeningCard } from "@/components/settings/listening-card";
import { ResetDemo } from "@/components/settings/reset-demo";
import { SpendingLimitsForm } from "@/components/settings/spending-limits-form";
import { PageTitle } from "@/components/shell/page-title";

export const Route = createFileRoute("/_app/settings")({
  loader: ({ context }) =>
    context.queryClient.query({ ...limitsQuery(), staleTime: "static" }),
  head: () => ({ meta: [{ title: "Settings · Stark" }] }),
  component: Settings,
});

function Settings() {
  const { data: limits } = useSuspenseQuery(limitsQuery());

  return (
    <>
      <PageTitle>Settings</PageTitle>

      <SectionHeading>Spending limits</SectionHeading>
      <SpendingLimitsForm limits={limits} />

      <SectionHeading>This account</SectionHeading>
      <AccountCard />

      <SectionHeading>How Stark listens</SectionHeading>
      <ListeningCard />

      {import.meta.env.DEV ? <ResetDemo /> : null}
    </>
  );
}
