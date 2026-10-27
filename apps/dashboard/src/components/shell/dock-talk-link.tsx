import { Icons } from "@stark/ui/components/icons";
import { Link } from "@tanstack/react-router";

export function DockTalkLink() {
  return (
    <Link
      to="/talk"
      aria-label="Talk to Stark"
      className="pointer-events-auto flex size-13.5 items-center justify-center rounded-full bg-brand text-white shadow-[0_12px_30px_rgba(0,0,0,0.5)]"
    >
      <Icons.Mic size={22} />
    </Link>
  );
}
