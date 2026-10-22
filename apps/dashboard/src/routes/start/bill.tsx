import { limitsQuery } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { formatNaira } from "@stark/utils/format";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { BillForm } from "@/components/bill-form";
import { OnboardingShell } from "@/components/onboarding-shell";

export const Route = createFileRoute("/start/bill")({
  head: () => ({ meta: [{ title: "Your first bill · Stark" }] }),
  component: FirstBill,
});

function FirstBill() {
  const navigate = useNavigate();
  const { data: limits } = useQuery(limitsQuery());
  return (
    <OnboardingShell
      step={2}
      title="What should Stark pay first?"
      lead="You can add more bills later, or just ask Stark."
    >
      <BillForm
        onAdded={() => navigate({ to: "/start/money" })}
        footer={
          <p className="m-0 flex items-start gap-2 text-[13px] text-fg-2">
            <Icons.Shield size={16} className="flex-none text-brand-warm" />
            <span>
              Stark always asks before paying
              {limits
                ? ` and won’t spend more than ${formatNaira(limits.monthly_cap_ngn)} a month`
                : ""}
              . <Link to="/settings">Change</Link>
            </span>
          </p>
        }
      />
      <Button
        variant="ghost"
        nativeButton={false}
        render={<Link to="/start/money" />}
        className="self-center"
      >
        Skip for now
      </Button>
    </OnboardingShell>
  );
}
