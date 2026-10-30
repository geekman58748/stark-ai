import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { BackLink } from "@/components/shell/back-link";
import { PageTitle } from "@/components/shell/page-title";
import { FundForm } from "@/components/wallet/fund-form";

export const Route = createFileRoute("/_app/wallet/add")({
  head: () => ({ meta: [{ title: "Add test money · Stark" }] }),
  component: AddTestMoney,
});

function AddTestMoney() {
  const navigate = useNavigate();
  return (
    <div className="flex w-full max-w-[480px] flex-col gap-6 self-center">
      <BackLink to="/wallet">Wallet</BackLink>
      <div className="flex flex-col gap-2">
        <PageTitle>Add test money</PageTitle>
        <p className="m-0 text-fg-2">Stark pays your bills from this balance.</p>
      </div>
      <FundForm onDone={() => navigate({ to: "/wallet" })} />
    </div>
  );
}
