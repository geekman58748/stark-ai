import type { tabs } from "@/components/shell/tabs";
import { usePath } from "@/components/shell/use-path";
import { NavMatch } from "@/lib/navigation/nav-match";
import { cn } from "@stark/ui/utils/cn";
import { Link } from "@tanstack/react-router";

export function TabBarItem({
  tab: { to, label, icon: Icon, exact },
}: {
  tab: (typeof tabs)[number];
}) {
  const path = usePath();
  return (
    <Link
      to={to}
      aria-current={NavMatch.isActive(path, to, exact) ? "page" : undefined}
      className={cn(
        "flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium no-underline",
        NavMatch.isActive(path, to, exact)
          ? "text-brand-soft"
          : "text-idle hover:text-fg",
      )}
    >
      <Icon size={22} />
      {label}
    </Link>
  );
}
