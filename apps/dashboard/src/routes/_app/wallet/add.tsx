import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import { BackLink } from "@/components/shell/back-link";
import { PageTitle } from "@/components/shell/page-title";
import { FundForm } from "@/components/wallet/fund-form";

export const Route = createFileRoute("/_app/wallet/add")({
  validateSearch: z.object({
    method: z.enum(["bank", "card", "crypto"]).optional(),
  }),
  head: () => ({ meta: [{ title: "Add money · Stark" }] }),
  component: AddMoney,
});

function AddMoney() {
  const navigate = useNavigate();
  const { method } = Route.useSearch();
  return (
    <div className="flex w-full max-w-[480px] flex-col gap-6 self-center">
      <BackLink to="/wallet">Wallet</BackLink>
      <div className="flex flex-col gap-2">
        <PageTitle>Add money</PageTitle>
        <p className="m-0 text-fg-2">
          Stark pays your bills from this balance.
        </p>
      </div>
      <FundForm
        initialMethod={method}
        onDone={() => navigate({ to: "/wallet" })}
      />
    </div>
  );
}
