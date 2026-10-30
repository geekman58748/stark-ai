import { stateQuery } from "@stark/api";
import { Avatar, AvatarFallback } from "@stark/ui/components/avatar";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

export function AccountAvatar() {
  const { data } = useQuery(stateQuery());
  const initials = data?.first_name?.slice(0, 2).toUpperCase() ?? "";
  return (
    <Link to="/settings" aria-label="Account and settings" className="rounded-full no-underline">
      <Avatar className="size-8.5">
        <AvatarFallback className="bg-surface-3 text-xs font-semibold text-fg">
          {initials}
        </AvatarFallback>
      </Avatar>
    </Link>
  );
}
