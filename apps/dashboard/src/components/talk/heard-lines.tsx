import { VoiceLine } from "@/components/talk/voice-line";

export function HeardLines({ heard }: { heard: string }) {
  return (
    <>
      <span className="text-xs text-muted-foreground">You</span>
      <VoiceLine key={heard} delay="0ms">
        “{heard}”
      </VoiceLine>
    </>
  );
}
