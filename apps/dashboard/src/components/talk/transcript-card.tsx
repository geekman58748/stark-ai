import { HeardLines } from "@/components/talk/heard-lines";
import { ReplyLines } from "@/components/talk/reply-lines";
import { TryLines } from "@/components/talk/try-lines";
import type { Stage } from "@/lib/talk/types";
import type { VoiceReply } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { cn } from "@stark/ui/utils/cn";

export function TranscriptCard({
  stage,
  reply,
  heard,
}: {
  stage: Stage;
  reply: VoiceReply | null;
  heard: string;
}) {
  return (
    <Card
      aria-live="polite"
      className={cn(
        "min-h-30 gap-2 rounded-[18px] border-white/10 bg-white/5 p-4 lg:min-h-48",
        stage === "thinking" && "voice-scan",
      )}
    >
      {reply?.reply ? (
        <ReplyLines reply={reply.reply} token={reply.token} />
      ) : heard ? (
        <HeardLines heard={heard} />
      ) : (
        <TryLines />
      )}
    </Card>
  );
}
