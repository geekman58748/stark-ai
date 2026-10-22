import { LogoMark } from "@stark/ui/logo";
import { Steps } from "@stark/ui/steps";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

/** Setup is three short steps: sign up, first bill, add money. */
export function OnboardingShell({
  step,
  title,
  lead,
  children,
}: {
  step: 1 | 2 | 3;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
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
        <span className="tabular ml-auto text-xs text-muted">{step} of 3</span>
      </header>
      <main className="mx-auto flex w-full max-w-[480px] flex-col gap-6 px-5 pt-8 pb-16 sm:pt-12">
        <Steps current={step} />
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
            {title}
          </h1>
          <p className="m-0 text-[15px] text-fg-2">{lead}</p>
        </div>
        {children}
      </main>
    </div>
  );
}
