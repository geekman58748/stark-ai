import { Icons } from "@stark/ui/components/icons";

export function PasswordRevealButton({
  revealed,
  onToggle,
}: {
  revealed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={revealed}
      aria-label={revealed ? "Hide password" : "Show password"}
      className="grid size-8 shrink-0 cursor-pointer place-items-center rounded-lg text-faint transition-colors hover:bg-white/5 hover:text-fg-2 focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-none"
    >
      {revealed ? <Icons.EyeOff size={17} /> : <Icons.Eye size={17} />}
    </button>
  );
}
