import { PageTitle } from "@/components/shell/page-title";
import { AddMoneyWays } from "@/components/wallet/add-money-ways";
import { MoneyMoves } from "@/components/wallet/money-moves";
import { WalletBalanceCard } from "@/components/wallet/wallet-balance-card";
import { activityQuery, walletQuery } from "@stark/api";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_app/wallet/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.query({ ...walletQuery(), staleTime: "static" }),
      context.queryClient.query({ ...activityQuery(), staleTime: "static" }),
    ]),
  head: () => ({ meta: [{ title: "Wallet · Stark" }] }),
  component: WalletPage,
});

function WalletPage() {
  const { data: wallet } = useSuspenseQuery(walletQuery());
  const { data: activity } = useSuspenseQuery(activityQuery());
  const moves = activity.filter(
    (r) => r.type === "deposit" || r.type === "withdrawal",
  );

  return (
    <>
      <PageTitle>Wallet</PageTitle>
      <WalletBalanceCard wallet={wallet} />

      <SectionHeading>Ways to add money</SectionHeading>
      <AddMoneyWays />

      <SectionHeading>Money in and out</SectionHeading>
      <MoneyMoves moves={moves} />
    </>
  );
}
