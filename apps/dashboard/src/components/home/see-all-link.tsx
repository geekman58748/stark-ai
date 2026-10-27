import { Link } from "@tanstack/react-router";

export function SeeAllLink({ to }: { to: "/bills" | "/activity" }) {
  return (
    <Link to={to} className="text-xs no-underline">
      See all
    </Link>
  );
}
