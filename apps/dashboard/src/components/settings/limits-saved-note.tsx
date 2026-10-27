import { Icons } from "@stark/ui/components/icons";

export function LimitsSavedNote() {
  return (
    <p
      aria-live="polite"
      className="m-0 flex items-center gap-2 text-[13px] text-fg-2"
    >
      <Icons.Check size={16} className="text-brand-warm" />
      Saved. Stark uses the new limits from its next payment.
    </p>
  );
}
