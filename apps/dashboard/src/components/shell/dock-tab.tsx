import type { tabs } from "@/components/shell/tabs";
import { usePath } from "@/components/shell/use-path";
import { NavMatch } from "@/lib/navigation/nav-match";
import { cn } from "@stark/ui/utils/cn";
import { Link } from "@tanstack/react-router";

export function DockTab({
  tab: { to, label, icon: Icon, exact },
}: {
  tab: (typeof tabs)[number];
}) {
  const path = usePath();
  return (
    <Link
      to={to}
      aria-label={label}
      aria-current={NavMatch.isActive(path, to, exact) ? "page" : undefined}
      className={cn(
        "flex size-10.5 items-center justify-center rounded-full text-fg",
        NavMatch.isActive(path, to, exact) && "bg-brand/25",
      )}
    >
      <Icon size={18} />
    </Link>
  );
}
