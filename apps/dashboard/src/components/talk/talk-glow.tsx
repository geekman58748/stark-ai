import { cn } from "@stark/ui/utils/cn";

export function TalkGlow({ live }: { live: boolean }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute top-40 left-1/2 size-130 -translate-x-1/2 rounded-full bg-brand blur-[120px] transition-all duration-700 ease-out lg:top-1/2 lg:left-[30%] lg:size-160 lg:-translate-y-1/2",
        live ? "opacity-45 scale-105" : "opacity-20",
      )}
    />
  );
}
