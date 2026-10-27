import { AUTH_CARD } from "@/components/auth/methods";
import { LogoMark } from "@stark/ui/components/logo";
import { Link } from "@tanstack/react-router";

export function AuthHeader({ step }: { step?: string }) {
  return (
    <header className="flex items-center justify-between gap-4">
      <Link
        to="/"
        aria-label="Stark home"
        className="flex items-center gap-2 text-fg no-underline hover:text-fg"
      >
        <LogoMark size={26} cutout={AUTH_CARD} />
        <span className="text-[15px] font-semibold">Stark</span>
      </Link>
      {step ? (
        <span className="tabular text-[12px] text-faint">{step}</span>
      ) : null}
    </header>
  );
}
