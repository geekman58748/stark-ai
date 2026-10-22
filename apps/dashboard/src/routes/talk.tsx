import { errorCopy, stateQuery, useVoice, type VoiceReply } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { Icons } from "@stark/ui/components/icons";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@stark/ui/components/input-group";
import { LogoMark } from "@stark/ui/components/logo";
import { cn } from "@stark/ui/utils/cn";
import { formatNaira, formatToken } from "@stark/utils/format";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { meterBill } from "@/lib/bills";
import { livePayments } from "@/lib/receipts";
import { createRecognition, type Recognition, transcriptOf } from "@/lib/speech";

export const Route = createFileRoute("/talk")({
  validateSearch: z.object({ q: z.string().optional() }),
  head: () => ({ meta: [{ title: "Talk · Stark" }] }),
  component: Talk,
});

type Stage = "idle" | "listening" | "thinking" | "done";

function addressed(text: string) {
  return /\bstark\b/i.test(text) ? text : `Stark, ${text}`;
}

function Talk() {
  const { q } = Route.useSearch();
  const { data: state } = useQuery(stateQuery());

  const voice = useVoice();
  const [stage, setStage] = useState<Stage>("idle");
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [reply, setReply] = useState<VoiceReply | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const sentQ = useRef(false);
  const [canListen, setCanListen] = useState(false);

  const handleSend = (transcript: string) => {
    setStage("thinking");
    voice.mutate(transcript, {
      onSuccess: (res) => {
        if (res.ignored) {
          setStage("idle");
          return;
        }
        setReply(res);
        setStage("done");
      },
      onError: () => setStage("done"),
    });
  };

  useEffect(() => setCanListen(createRecognition() !== null), []);

  useEffect(() => {
    if (q && !sentQ.current) {
      sentQ.current = true;
      setHeard(q);
      handleSend(addressed(q));
    }
  }, [q]);

  const handleTapMicrophone = () => {
    if (stage === "listening") {
      recognition.current?.stop();
      return;
    }
    const r = createRecognition();
    if (!r) {
      document.getElementById("type-instead")?.focus();
      return;
    }
    recognition.current = r;
    let text = "";
    r.onresult = (e) => {
      text = transcriptOf(e);
      setHeard(text);
    };
    r.onerror = () => setStage("idle");
    r.onend = () => (text.trim() ? handleSend(text.trim()) : setStage("idle"));
    setHeard("");
    setReply(null);
    voice.reset();
    setStage("listening");
    r.start();
  };

  const live = stage === "listening" || stage === "thinking";
  const meter = state ? meterBill(state) : undefined;

  const copy = {
    idle: [
      "Tap and speak",
      canListen ? "Start with “Stark”, then say what you need." : "Type what you need below.",
    ],
    listening: ["Listening…", "Tap again when you’re done."],
    thinking: ["One moment", "Checking your bills and balance."],
    done: voice.error
      ? ["Couldn’t reach Stark", errorCopy(voice.error)]
      : ["Done", "Here’s what Stark said."],
  }[stage];

  return (
    <div className="relative mx-auto flex min-h-dvh max-w-120 flex-col gap-5 overflow-hidden bg-[#111211] px-6 pt-7 pb-8">
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-40 left-1/2 size-130 -translate-x-1/2 rounded-full bg-brand blur-[120px] transition-opacity duration-500",
          live ? "opacity-45" : "opacity-20",
        )}
      />

      <header className="relative flex items-center justify-between">
        <span className="flex items-center gap-2">
          <LogoMark cutout="#111211" />
          <span className="font-serif text-[19px] font-semibold tracking-[-0.02em]">Stark</span>
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Close"
          nativeButton={false}
          render={<Link to="/" />}
          className="size-9"
        >
          <Icons.Close className="size-5" />
        </Button>
      </header>

      {state ? (
        <section aria-label="Status" className="relative grid grid-cols-2 gap-2">
          {meter && state.days_left !== null ? (
            <Card size="sm" className="gap-0 rounded-row border-white/8 bg-white/5">
              <span className="text-xs text-muted-foreground">{meter.label} meter</span>
              <span className="font-serif text-xl">~{state.days_left} days</span>
            </Card>
          ) : null}
          <Card size="sm" className="gap-0 rounded-row border-white/8 bg-white/5">
            <span className="text-xs text-muted-foreground">Limit left</span>
            <span className="font-serif text-xl">{formatNaira(state.remaining_cap_ngn)}</span>
          </Card>
        </section>
      ) : null}

      <div className="relative flex flex-1 flex-col items-center justify-center gap-6 text-center">
        <Button
          variant="ghost"
          onClick={handleTapMicrophone}
          disabled={stage === "thinking"}
          aria-label={stage === "listening" ? "Stop recording" : "Talk to Stark"}
          className={cn(
            "size-50 rounded-full",
            live
              ? "border-0 bg-brand-warm text-canvas-deep shadow-[0_0_0_16px_rgba(194,65,12,0.18),0_0_0_36px_rgba(194,65,12,0.08)] hover:bg-brand-warm hover:text-canvas-deep"
              : "border-white/16 bg-[#1a1b1a] text-fg shadow-[0_0_0_16px_rgba(255,255,255,0.03)] hover:bg-[#1f201f] hover:text-fg",
          )}
        >
          <Icons.Mic className="size-14" />
        </Button>
        <div className="flex min-h-16 flex-col gap-1.5">
          <span className="font-serif text-[26px] tracking-[-0.02em]">{copy[0]}</span>
          <span className="text-sm text-muted-foreground">{copy[1]}</span>
        </div>
      </div>

      <Card
        aria-live="polite"
        className="relative min-h-30 gap-2 rounded-[18px] border-white/10 bg-white/5 p-4"
      >
        {reply?.reply ? (
          <>
            <span className="text-xs text-muted-foreground">Stark</span>
            <span>{reply.reply}</span>
            {reply.token ? (
              <span className="tabular text-lg tracking-[0.03em]">{formatToken(reply.token)}</span>
            ) : null}
          </>
        ) : heard ? (
          <>
            <span className="text-xs text-muted-foreground">You</span>
            <span>“{heard}”</span>
          </>
        ) : (
          <>
            <span className="text-xs text-muted-foreground">Try</span>
            <span>“Stark, top up the house with five thousand.”</span>
          </>
        )}
      </Card>

      <form
        className="relative m-0"
        onSubmit={(e) => {
          e.preventDefault();
          const text = typed.trim();
          if (!text) return;
          setHeard(text);
          setReply(null);
          setTyped("");
          handleSend(addressed(text));
        }}
      >
        <InputGroup className="h-auto rounded-full border-white/10 bg-white/5 py-1.5 pr-1.5 pl-4 dark:bg-white/5">
          <InputGroupInput
            id="type-instead"
            aria-label="Type instead"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Or type it"
            className="h-auto px-0 py-2 text-[15px]"
          />
          <InputGroupAddon align="inline-end" className="py-0">
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              aria-label="Send"
              disabled={!typed.trim() || stage === "thinking"}
              className="size-9 rounded-full"
            >
              <Icons.ArrowRight />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </form>

      <span className="relative text-center text-xs text-muted-foreground">
        This screen can’t spend on its own. Stark checks every payment against your limits.
        {livePayments ? "" : " Tokens are samples for now."}
      </span>
    </div>
  );
}
