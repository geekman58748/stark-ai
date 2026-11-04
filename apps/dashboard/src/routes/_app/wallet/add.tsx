import { fundingMethodsQuery } from "@stark/api/queries";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import { BackLink } from "@/components/shell/back-link";
import { PageTitle } from "@/components/shell/page-title";
import { AddMoneyForm } from "@/components/wallet/add-money-form";
import { DepositStatus } from "@/components/wallet/deposit-status";

export const Route = createFileRoute("/_app/wallet/add")({
  // `deposit` is set when Bachs's checkout sends the user back here.
  validateSearch: z.object({ deposit: z.string().optional() }),
  loader: ({ context }) => context.queryClient.query(fundingMethodsQuery()),
  head: () => ({ meta: [{ title: "Add money · Stark" }] }),
  component: AddMoney,
});

function AddMoney() {
  const { deposit } = Route.useSearch();
  const navigate = useNavigate();
  const { data: methods } = useSuspenseQuery(fundingMethodsQuery());

  return (
    <div className="flex w-full max-w-120 flex-col gap-6 self-center">
      <BackLink to="/wallet">Wallet</BackLink>
      <div className="flex flex-col gap-2">
        <PageTitle>Add money</PageTitle>
        <p className="m-0 text-fg-2">
          Stark pays your bills from this balance. It’s ready to spend as soon as it lands.
        </p>
      </div>
      {deposit ? (
        <DepositStatus depositId={deposit} />
      ) : (
        <AddMoneyForm
          methods={methods}
          onStarted={(started) => navigate({ to: ".", search: { deposit: started.id } })}
          onTestMoneyAdded={() => navigate({ to: "/wallet" })}
        />
      )}
    </div>
  );
}
