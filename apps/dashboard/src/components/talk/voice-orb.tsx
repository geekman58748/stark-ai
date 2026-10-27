import { MicButton } from "@/components/talk/mic-button";
import { OrbHalo } from "@/components/talk/orb-halo";
import { VoiceEq } from "@/components/talk/voice-eq";
import type { Stage } from "@/lib/talk/types";

export function VoiceOrb({
  stage,
  live,
  onTap,
}: {
  stage: Stage;
  live: boolean;
  onTap: () => void;
}) {
  return (
    <div
      className="voice-orb flex flex-col items-center gap-5"
      data-state={stage}
    >
      <div className="relative grid place-items-center">
        <OrbHalo />
        <MicButton stage={stage} live={live} onTap={onTap} />
      </div>
      <VoiceEq />
    </div>
  );
}
