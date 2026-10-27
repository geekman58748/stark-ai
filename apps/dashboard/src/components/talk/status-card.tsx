import { Card } from "@stark/ui/components/card";
import type { ReactNode } from "react";

export function StatusCard({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <Card size="sm" className="gap-0 rounded-row border-white/8 bg-white/5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-serif text-xl">{children}</span>
    </Card>
  );
}
