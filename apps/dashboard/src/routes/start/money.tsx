import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FundForm } from "@/components/fund-form";
import { OnboardingShell } from "@/components/onboarding-shell";

export const Route = createFileRoute("/start/money")({
  head: () => ({ meta: [{ title: "Add money · Stark" }] }),
  component: AddMoney,
});

function AddMoney() {
  const navigate = useNavigate();
  return (
    <OnboardingShell
      step={3}
      title="Add money for your bills"
      lead="Stark pays from this balance. Top it up whenever you like."
    >
      <FundForm onDone={() => navigate({ to: "/" })} />
      <Link to="/" className="self-center text-sm text-fg-2 no-underline hover:text-fg">
        Skip for now
      </Link>
    </OnboardingShell>
  );
}
