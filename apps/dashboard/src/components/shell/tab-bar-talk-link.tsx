import { Icons } from "@stark/ui/components/icons";
import { Link } from "@tanstack/react-router";

export function TabBarTalkLink() {
  return (
    <Link to="/talk" aria-label="Talk to Stark" className="flex flex-1 justify-center">
      <span className="-mt-5.5 flex size-14 items-center justify-center rounded-full border-4 border-canvas bg-brand text-white shadow-[0_8px_24px_rgba(194,65,12,0.45)]">
        <Icons.Mic size={24} />
      </span>
    </Link>
  );
}
