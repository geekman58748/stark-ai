import { Button } from "@stark/ui/components/button";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { OnboardingShell } from "@/components/shell/onboarding-shell";
import { FundForm } from "@/components/wallet/fund-form";

export const Route = createFileRoute("/start/money")({
  head: () => ({ meta: [{ title: "Add test money · Stark" }] }),
  component: AddMoney,
});

function AddMoney() {
  const navigate = useNavigate();
  return (
    <OnboardingShell
      step={3}
      title="Add test money for your bills"
      lead="Stark pays from this balance. Top it up whenever you like."
    >
      <FundForm onDone={() => navigate({ to: "/" })} />
      <Button variant="ghost" nativeButton={false} render={<Link to="/" />} className="self-center">
        Skip for now
      </Button>
    </OnboardingShell>
  );
}
