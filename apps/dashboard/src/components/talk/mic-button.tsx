import type { Stage } from "@/lib/talk/types";
import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { cn } from "@stark/ui/utils/cn";

export function MicButton({
  stage,
  live,
  onTap,
}: {
  stage: Stage;
  live: boolean;
  onTap: () => void;
}) {
  return (
    <Button
      variant="ghost"
      onClick={onTap}
      disabled={stage === "thinking"}
      aria-label={stage === "listening" ? "Stop recording" : "Talk to Stark"}
      className={cn(
        "relative z-10 size-50 rounded-full lg:size-64",
        live
          ? "border-0 bg-brand-warm text-canvas-deep shadow-[0_0_0_16px_rgba(194,65,12,0.18),0_0_0_36px_rgba(194,65,12,0.08)] hover:bg-brand-warm hover:text-canvas-deep"
          : "border-white/16 bg-[#1a1b1a] text-fg shadow-[0_0_0_16px_rgba(255,255,255,0.03)] hover:bg-[#1f201f] hover:text-fg",
      )}
    >
      <Icons.Mic className="size-14 lg:size-18" />
    </Button>
  );
}
