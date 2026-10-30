import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      nativeButton={false}
      render={<Link to={to} />}
      className="-ml-1 self-start px-1"
    >
      <Icons.ChevronLeft size={16} />
      {children}
    </Button>
  );
}
