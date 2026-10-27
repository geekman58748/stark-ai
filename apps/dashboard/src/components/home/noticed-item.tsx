import type { Suggestion } from "@stark/api";
import { cn } from "@stark/ui/utils/cn";

export function NoticedItem({ suggestion }: { suggestion: Suggestion }) {
  return (
    <div className="flex items-start gap-2.5">
      <span
        aria-hidden="true"
        className={cn(
          "mt-1.5 size-1.5 shrink-0 rounded-full",
          suggestion.severity === "alert"
            ? "bg-destructive"
            : suggestion.severity === "warn"
              ? "bg-brand-warm"
              : "bg-faint",
        )}
      />
      <span className="text-sm leading-relaxed">{suggestion.text}</span>
    </div>
  );
}
