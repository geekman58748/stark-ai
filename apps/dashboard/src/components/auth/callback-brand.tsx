import { LogoMark } from "@stark/ui/components/logo";
import { Link } from "@tanstack/react-router";
import { AUTH_CARD } from "@/components/auth/methods";

export function CallbackBrand() {
  return (
    <Link to="/" className="flex items-center gap-2 text-fg no-underline">
      <LogoMark size={26} cutout={AUTH_CARD} />
      <span className="text-[15px] font-semibold">Stark</span>
    </Link>
  );
}
