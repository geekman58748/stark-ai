import { LogoMark } from "@stark/ui/components/logo";
import { Link } from "@tanstack/react-router";

export function OnboardingHeader({ step }: { step: 1 | 2 | 3 }) {
  return (
    <header className="flex items-center gap-3 border-b border-line px-5 py-3.5">
      <Link
        to="/"
        aria-label="Stark home"
        className="flex items-center gap-2 text-fg no-underline hover:text-fg"
      >
        <LogoMark />
        <span className="text-[15px] font-semibold">Stark</span>
      </Link>
      <span aria-hidden="true" className="text-faint">
        /
      </span>
      <span className="text-[13px] font-medium">Get started</span>
      <span className="tabular ml-auto text-xs text-muted-foreground">
        {step} of 3
      </span>
    </header>
  );
}
