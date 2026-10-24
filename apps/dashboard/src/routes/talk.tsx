import { api, errorCopy, stateQuery, useVoice, useVoiceAudio, type VoiceReply } from "@stark/api";
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
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { isPayable, meterBill } from "@/lib/bills";
import { livePayments } from "@/lib/receipts";
import { nextRenewal, renewalWhen } from "@/lib/renewals";
import { createRecognition, isSleepIntent, type Recognition, transcriptOf } from "@/lib/speech";

export const Route = createFileRoute("/talk")({
  validateSearch: z.object({ q: z.string().optional() }),
  head: () => ({ meta: [{ title: "Talk · Stark" }] }),
  component: Talk,
});

type Stage = "idle" | "listening" | "thinking" | "done";

/** Nothing times the session out. The mic stays open after every answer until the
 *  user taps the orb or says they are done, so "Stark" is said once per conversation,
 *  not once per question — and a pause to think is not a dismissal. */
/** Chrome wants a beat between utterances before the recognizer restarts. */
const RESTART_MS = 350;
/** Equaliser bars — heights and delays fixed up front so nothing reflows. */
const EQ_BARS = Array.from(
  { length: 12 },
  (_, i) =>
    ({
      "--i": `${(i % 6) * 60}ms`,
      "--d": `${600 + ((i * 137) % 460)}ms`,
    }) as CSSProperties,
);

function addressed(text: string) {
  return /\bstark\b/i.test(text) ? text : `Stark, ${text}`;
}

/** Recording, for browsers without the Web Speech API: the clip goes up and
 *  the server hears it (POST /v1/voice with real audio). */
function canRecord() {
  return (
    typeof MediaRecorder !== "undefined" &&
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}

/** How long one tap records. Long enough for a question, short enough to not
 *  feel like a voicemail. */
const RECORD_MS = 8_000;

/** Why the browser gave up on the mic — always shown, never swallowed. */
function micErrorCopy(error?: string) {
  if (error === "not-allowed" || error === "service-not-allowed") {
    return "Microphone blocked — allow mic access for this page, or type below.";
  }
  if (error === "no-speech") {
    return "I didn't hear anything. Tap and try again.";
  }
  return "I didn't catch that — tap to try again, or type below.";
}

function Talk() {
  const { q } = Route.useSearch();
  const { data: state } = useQuery(stateQuery());

  const voice = useVoice();
  const voiceAudio = useVoiceAudio();
  const [stage, setStage] = useState<Stage>("idle");
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [reply, setReply] = useState<VoiceReply | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [session, setSession] = useState(false);
  const [canListen, setCanListen] = useState(false);
  const recognition = useRef<Recognition | null>(null);
  const sentQ = useRef(false);
  const player = useRef<HTMLAudioElement | null>(null);
  const speakSeq = useRef(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const recordStop = useRef<number | null>(null);
  const disposed = useRef(false);

  // Hands-free machinery. Refs, not state: these live inside callbacks that
  // outlive a render, and none of them need to draw anything by themselves.
  const stageRef = useRef<Stage>("idle");
  /** Awake = the user wants the mic on. No clock: the session ends on their word. */
  const awake = useRef(false);
  const restartTimer = useRef<number | null>(null);
  const micWanted = useRef(false);
  const stopRequested = useRef(false);
  const fatalError = useRef(false);
  const speaking = useRef(false);

  const go = (next: Stage) => {
    stageRef.current = next;
    setStage(next);
  };

  const inSession = () => awake.current;

  const endSession = () => {
    awake.current = false;
    micWanted.current = false;
    if (restartTimer.current !== null) {
      window.clearTimeout(restartTimer.current);
      restartTimer.current = null;
    }
    // Null first: the recognizer's own onend then sees it was superseded and
    // stays quiet, so closing a session can never restart itself.
    const r = recognition.current;
    recognition.current = null;
    stopRequested.current = false;
    try {
      r?.stop();
    } catch {
      /* already finished */
    }
    setSession(false);
  };

  const closeIdle = () => {
    endSession();
    go("idle");
  };

  const stopSpeaking = () => {
    speaking.current = false;
    player.current?.pause();
    player.current = null;
  };

  const scheduleRestart = () => {
    if (restartTimer.current !== null || !micWanted.current) return;
    restartTimer.current = window.setTimeout(() => {
      restartTimer.current = null;
      listen();
    }, RESTART_MS);
  };

  /** Finish one recorded clip: stop timers, release the mic, send it up. */
  const stopRecording = () => {
    if (recordStop.current !== null) {
      window.clearTimeout(recordStop.current);
      recordStop.current = null;
    }
    const rec = recorder.current;
    recorder.current = null;
    if (rec && rec.state !== "inactive") {
      try {
        rec.stop();
      } catch {
        /* already stopped */
      }
    }
  };

  /** No browser recognizer: record a clip and let the server's STT hear it.
   *  Tap again to stop early; after RECORD_MS it sends itself. */
  const recordThenSend = () => {
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        const rec = new MediaRecorder(stream);
        const parts: BlobPart[] = [];
        rec.ondataavailable = (e) => {
          if (e.data.size) parts.push(e.data);
        };
        rec.onstop = () => {
          if (recordStop.current !== null) {
            window.clearTimeout(recordStop.current);
            recordStop.current = null;
          }
          recorder.current = null;
          stream.getTracks().forEach((t) => {
            t.stop();
          });
          if (disposed.current) return;
          const blob = new Blob(parts, { type: rec.mimeType || "audio/webm" });
          if (blob.size < 1024) {
            closeIdle();
            setNotice("I didn't hear that. Tap and try again, or type below.");
            return;
          }
          go("thinking");
          voiceAudio.mutate(blob, {
            onSuccess: (res) => {
              if (res.ignored) {
                if (import.meta.env.DEV) {
                  console.debug("[wake] ignored (audio):", res.transcript);
                }
                closeIdle();
                setNotice(
                  "Start with “Hey Stark” — then say what you need; typos and accents are fine.",
                );
                return;
              }
              // The recorded-audio path never reaches `submit`, so the dismissal
              // is checked here too — a session must end the same way on every door.
              if (isSleepIntent(res.transcript)) {
                endSession();
                go("idle");
                setHeard(res.transcript);
                setNotice("Asleep. Tap the mic when you need me.");
                speak("Okay. I'll be here — tap the mic when you need me.");
                return;
              }
              setHeard(res.transcript);
              setReply(res);
              go("done");
              if (res.reply) speak(res.reply);
              else scheduleRestart();
            },
            onError: () => {
              go("done");
              scheduleRestart();
            },
          });
        };
        recorder.current = rec;
        rec.start();
        go("listening");
        recordStop.current = window.setTimeout(() => {
          recordStop.current = null;
          if (rec.state !== "inactive") rec.stop();
        }, RECORD_MS);
      })
      .catch(() => {
        closeIdle();
        setNotice(micErrorCopy("not-allowed"));
      });
  };

  /** The clip finished (or never started): hands free again, if we still own the mic. */
  const finishPlayback = (a: HTMLAudioElement) => {
    if (player.current !== a) return;
    player.current = null;
    speaking.current = false;
    scheduleRestart();
  };

  /** The voice for a reply we already have: fetched after the words land, so
   *  text is never hostage to synthesis. A stale fetch never plays over a new
   *  question, and an autoplay refusal is fine — the text is on screen.
   *
   *  The stream comes first (it plays from the first bytes rather than after
   *  the whole clip is built); the buffered voice is the floor if it refuses. */
  const speak = (text: string) => {
    const seq = ++speakSeq.current;
    stopSpeaking();
    speaking.current = true;
    const play = (src: string) => {
      const a = new Audio(src);
      player.current = a;
      a.addEventListener("ended", () => finishPlayback(a));
      a.addEventListener("error", () => finishPlayback(a));
      void a.play().catch(() => {
        // Autoplay refused: the words are on screen, so go back to listening
        // instead of waiting for a clip that will never start.
        if (player.current === a) finishPlayback(a);
      });
      return a;
    };
    const streamed = play(api.speakStreamUrl(text));
    let fellBack = false;
    streamed.addEventListener("error", () => {
      if (fellBack || seq !== speakSeq.current) return;
      fellBack = true;
      api
        .speak(text)
        .then(({ audio }) => {
          if (!audio || seq !== speakSeq.current) return;
          if (player.current === streamed) {
            player.current.pause();
            player.current = null;
          }
          speaking.current = true;
          play(audio);
        })
        .catch(() => undefined);
    });
  };

  const submit = (said: string, opts: { address?: boolean } = {}) => {
    // The one way to end a session without a tap. Checked here, before the
    // server, because "go to sleep" is not a question about their bills.
    if (isSleepIntent(said)) {
      endSession();
      go("idle");
      setHeard(said);
      setNotice("Asleep. Tap the mic when you need me.");
      speak("Okay. I'll be here — tap the mic when you need me.");
      return;
    }
    stopSpeaking();
    setNotice(null);
    setReply(null);
    go("thinking");
    // Inside a session the words are addressed without hearing "Stark" again —
    // the same prefix typing and `?q=` already use. Outside one the transcript
    // goes exactly as heard, so the server's wake gate still decides.
    const transcript = opts.address || inSession() ? addressed(said) : said;
    voice.mutate(transcript, {
      onSuccess: (res) => {
        if (res.ignored) {
          // DEV-only: the transcript that failed the gate is exactly the data
          // wake.py's alias set is tuned against.
          if (import.meta.env.DEV) console.debug("[wake] ignored:", said);
          closeIdle();
          setNotice("Start with “Hey Stark” — then say what you need; typos and accents are fine.");
          return;
        }
        setReply(res);
        go("done");
        if (res.reply) speak(res.reply);
        else scheduleRestart();
      },
      onError: () => {
        go("done");
        scheduleRestart();
      },
    });
  };

  /** One utterance. Returns only when the recognizer ends, then decides:
   *  speak → send, silence → keep listening (the hands-free loop), user asked
   *  to stop → sleep, an actual error → say why and sleep. */
  const listen = () => {
    if (recognition.current) return;
    if (stageRef.current === "thinking" || speaking.current) return;
    if (!micWanted.current || !awake.current) {
      go("idle");
      return;
    }
    const r = createRecognition();
    if (!r) {
      if (canRecord()) {
        // Server-side hearing: no browser recognizer, so record and upload.
        recordThenSend();
        return;
      }
      micWanted.current = false;
      go("idle");
      setNotice("This browser can’t listen — type what you need below.");
      document.getElementById("type-instead")?.focus();
      return;
    }

    fatalError.current = false;
    stopRequested.current = false;
    recognition.current = r;
    let text = "";

    r.onresult = (e) => {
      text = transcriptOf(e);
      setHeard(text);
    };

    r.onerror = (e) => {
      const error = e.error;
      if (error === "no-speech" || error === "aborted") return; // transient
      fatalError.current = true;
      closeIdle();
      setNotice(micErrorCopy(error));
    };

    r.onend = () => {
      if (recognition.current !== r) return; // superseded or session closed
      recognition.current = null;
      const said = text.trim();
      if (said) {
        submit(said);
        return;
      }
      if (stopRequested.current) {
        closeIdle();
        return;
      }
      if (fatalError.current) return;
      if (!micWanted.current || !awake.current) {
        closeIdle();
        setNotice("I didn’t hear that. Tap and try again, or type below.");
        return;
      }
      scheduleRestart(); // nobody spoke — keep listening until they say they are done
    };

    go("listening");
    try {
      r.start();
    } catch {
      // Chrome refuses a start that races the previous stop (InvalidStateError).
      // Sleeping silently here is how a session used to die mid-conversation with
      // the orb just going idle: say what happened instead.
      recognition.current = null;
      go("idle");
      setNotice("The mic didn’t restart — tap the orb, or type below.");
      closeIdle();
    }
  };

  const handleTapMicrophone = () => {
    if (stageRef.current === "listening") {
      // Recording (no recognizer): a second tap finishes and sends the clip.
      if (recorder.current) {
        stopRecording();
        return;
      }
      stopRequested.current = true;
      recognition.current?.stop();
      return;
    }
    stopSpeaking();
    setNotice(null);
    if (!canListen) {
      document.getElementById("type-instead")?.focus();
      return;
    }
    micWanted.current = true;
    awake.current = true;
    setSession(true);
    listen();
  };

  useEffect(
    () => () => {
      disposed.current = true;
      endSession();
      stopSpeaking();
      if (recordStop.current !== null) window.clearTimeout(recordStop.current);
      const rec = recorder.current;
      recorder.current = null;
      if (rec && rec.state !== "inactive") {
        try {
          rec.stop();
        } catch {
          /* already stopped */
        }
      }
    },
    [],
  );

  useEffect(() => setCanListen(createRecognition() !== null || canRecord()), []);

  // A hidden tab cannot keep listening honestly — browsers throttle or kill the
  // recognizer, so it would look awake and hear nothing. Sleep with a reason
  // instead of staying half-awake behind another window.
  useEffect(() => {
    const onHidden = () => {
      if (document.visibilityState !== "hidden" || !awake.current) return;
      endSession();
      go("idle");
      setNotice("Asleep — the mic stops while this tab is hidden. Tap to wake me.");
    };
    document.addEventListener("visibilitychange", onHidden);
    return () => document.removeEventListener("visibilitychange", onHidden);
  }, []);

  useEffect(() => {
    if (q && !sentQ.current) {
      sentQ.current = true;
      setHeard(q);
      submit(q, { address: true });
    }
  }, [q]);

  const live = stage === "listening" || stage === "thinking";
  const meter = state ? meterBill(state) : undefined;
  const due = nextRenewal(state?.due_soon);

  const copy = {
    idle: [
      "Tap and speak",
      canListen ? "Start with “Hey Stark”, then say what you need." : "Type what you need below.",
    ],
    listening: [
      "Listening…",
      session
        ? "Keep going — you only say Stark once."
        : "Start with “Hey Stark”, then say what you need.",
    ],
    thinking: ["One moment", "Checking your bills and balance."],
    done:
      voice.error || voiceAudio.error
        ? ["Couldn’t reach Stark", errorCopy(voice.error ?? voiceAudio.error)]
        : session
          ? ["Still listening", "Say your next question whenever."]
          : ["Done", "Here’s what Stark said."],
  }[stage];

  return (
    <div className="relative flex min-h-dvh flex-col gap-5 overflow-hidden bg-[#111211] px-6 pt-7 pb-8 sm:px-10 lg:gap-0 lg:px-16">
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute top-40 left-1/2 size-130 -translate-x-1/2 rounded-full bg-brand blur-[120px] transition-all duration-700 ease-out lg:top-1/2 lg:left-[30%] lg:size-160 lg:-translate-y-1/2",
          live ? "opacity-45 scale-105" : "opacity-20",
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

      <div className="relative mx-auto flex w-full max-w-120 flex-1 flex-col gap-5 lg:grid lg:max-w-6xl lg:grid-cols-[1fr_minmax(0,440px)] lg:items-center lg:gap-16 lg:py-10">
        <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center lg:gap-8">
          <div className="voice-orb flex flex-col items-center gap-5" data-state={stage}>
            <div className="relative grid place-items-center">
              <span aria-hidden="true" className="voice-aura" />
              <span aria-hidden="true" className="voice-ring" />
              <span aria-hidden="true" className="voice-ring voice-ring-2" />
              <span aria-hidden="true" className="voice-orbit" />
              <Button
                variant="ghost"
                onClick={handleTapMicrophone}
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
            </div>
            <div className="voice-eq" aria-hidden="true">
              {EQ_BARS.map((style, i) => (
                <i key={i} style={style} />
              ))}
            </div>
          </div>

          <div
            key={stage}
            className="flex min-h-16 flex-col gap-1.5 animate-in fade-in slide-in-from-bottom-2 duration-300"
          >
            <span className="font-serif text-[26px] tracking-[-0.02em] lg:text-4xl">{copy[0]}</span>
            <span className="text-sm text-muted-foreground lg:text-base">{copy[1]}</span>
            {notice ? <span className="text-sm text-brand-warm">{notice}</span> : null}
          </div>
        </div>

        <div className="contents lg:flex lg:flex-col lg:gap-5">
          {state ? (
            <section aria-label="Status" className="order-first grid grid-cols-2 gap-2 lg:order-0">
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
              {due ? (
                // The reminder the server already judged due. It goes to the pay
                // screen rather than paying on a tap: one spend path, one confirm.
                <Link
                  to={isPayable(due) ? "/pay" : "/bills/$billId"}
                  search={
                    isPayable(due)
                      ? { bill: due.id, amount: due.price_ngn ?? undefined }
                      : undefined
                  }
                  params={isPayable(due) ? undefined : { billId: due.id }}
                  className="col-span-2 rounded-row no-underline lg:col-span-1"
                >
                  <Card
                    size="sm"
                    className={cn(
                      "h-full gap-0 rounded-row border-white/8 bg-white/5 transition-colors hover:border-white/25",
                      due.days_until <= 0 && "border-brand-warm/40 bg-brand-warm/10",
                    )}
                  >
                    <span className="text-xs text-muted-foreground">{due.label} renews</span>
                    <span
                      className={cn(
                        "font-serif text-xl",
                        due.days_until <= 0 ? "text-brand-warm" : "text-fg",
                      )}
                    >
                      {renewalWhen(due.days_until)}
                    </span>
                  </Card>
                </Link>
              ) : null}
            </section>
          ) : null}

          <Card
            aria-live="polite"
            className={cn(
              "min-h-30 gap-2 rounded-[18px] border-white/10 bg-white/5 p-4 lg:min-h-48",
              stage === "thinking" && "voice-scan",
            )}
          >
            {reply?.reply ? (
              <>
                <span
                  key={`who-${reply.reply}`}
                  className="voice-in text-xs text-muted-foreground"
                  style={{ "--d": "0ms" } as CSSProperties}
                >
                  Stark
                </span>
                <span
                  key={reply.reply}
                  className="voice-in"
                  style={{ "--d": "60ms" } as CSSProperties}
                >
                  {reply.reply}
                </span>
                {reply.token ? (
                  <span
                    key={reply.token}
                    className="voice-in tabular text-lg tracking-[0.03em]"
                    style={{ "--d": "140ms" } as CSSProperties}
                  >
                    {formatToken(reply.token)}
                  </span>
                ) : null}
              </>
            ) : heard ? (
              <>
                <span className="text-xs text-muted-foreground">You</span>
                <span key={heard} className="voice-in" style={{ "--d": "0ms" } as CSSProperties}>
                  “{heard}”
                </span>
              </>
            ) : (
              <>
                <span className="text-xs text-muted-foreground">Try</span>
                <span>“Stark, top up the house with five thousand.”</span>
              </>
            )}
          </Card>

          <form
            className="m-0"
            onSubmit={(e) => {
              e.preventDefault();
              const text = typed.trim();
              if (!text) return;
              setHeard(text);
              setReply(null);
              setTyped("");
              submit(text, { address: true });
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

          <span className="text-center text-xs text-muted-foreground lg:text-left">
            This screen can’t spend on its own. Stark checks every payment against your limits.
            {livePayments ? "" : " Tokens are samples for now."}
          </span>
        </div>
      </div>
    </div>
  );
}
