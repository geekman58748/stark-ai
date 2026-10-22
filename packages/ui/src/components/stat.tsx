import type { ReactNode } from "react";
import { cn } from "../utils/cn";
import { Eyebrow } from "./eyebrow";

export function StatGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4", className)}>
      {children}
    </div>
  );
}

export function Stat({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 border-t border-white/8 pt-3.5">
      <Eyebrow>{label}</Eyebrow>
      <span className="text-[15px] text-fg">{children}</span>
    </div>
  );
}
