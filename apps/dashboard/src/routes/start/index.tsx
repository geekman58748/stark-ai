import { buttonVariants } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { cn } from "@stark/ui/utils/cn";
import { createFileRoute, Link } from "@tanstack/react-router";
import { OnboardingShell } from "@/components/onboarding-shell";

export const Route = createFileRoute("/start/")({
  head: () => ({ meta: [{ title: "Sign up · Stark" }] }),
  component: SignUp,
});

// Sign-in isn't wired yet (the API has no auth), so each option continues to the next step.
function SignUp() {
  const option = "text-[15px] gap-2.5";
  return (
    <OnboardingShell
      step={1}
      title="Never run out of light again."
      lead="Create your Stark account. It takes about a minute."
    >
      <div className="flex flex-col gap-2.5">
        <Link
          to="/start/bill"
          className={cn(
            buttonVariants({ variant: "light", size: "lg", block: true }),
            option,
            "hover:text-canvas-deep",
          )}
        >
          <span aria-hidden="true" className="font-semibold">
            G
          </span>
          Continue with Google
        </Link>
        <Link
          to="/start/bill"
          className={cn(
            buttonVariants({ variant: "secondary", size: "lg", block: true }),
            option,
            "hover:text-fg",
          )}
        >
          <Icons.Phone size={16} />
          Continue with phone number
        </Link>
        <Link
          to="/start/bill"
          className={cn(
            buttonVariants({ variant: "secondary", size: "lg", block: true }),
            option,
            "hover:text-fg",
          )}
        >
          <Icons.Telegram size={16} />
          Continue in Telegram
        </Link>
      </div>
      <Card className="flex-row items-start gap-3">
        <IconTile>
          <Icons.Lock size={16} />
        </IconTile>
        <span className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">Your money stays yours</span>
          <span className="text-[13px] text-muted-foreground">
            Stark can only pay the bills you add, inside limits only you can change.
          </span>
        </span>
      </Card>
      <p className="m-0 text-center text-xs text-muted-foreground">
        Already have an account? <Link to="/">Log in</Link>
      </p>
    </OnboardingShell>
  );
}
