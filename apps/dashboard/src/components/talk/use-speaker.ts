import { api } from "@stark/api";
import { useRef } from "react";

/** Plays Stark's replies; `onFinished` runs once a clip ends (or never starts). */
export function useSpeaker(onFinished: () => void) {
  const player = useRef<HTMLAudioElement | null>(null);
  const speakSeq = useRef(0);
  const speaking = useRef(false);

  const stopSpeaking = () => {
    speaking.current = false;
    player.current?.pause();
    player.current = null;
  };

  /** The clip finished (or never started): hands free again, if we still own the mic. */
  const finishPlayback = (a: HTMLAudioElement) => {
    if (player.current !== a) return;
    player.current = null;
    speaking.current = false;
    onFinished();
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

    /** A stream refuses twice (once for the load, once for play()); one fetch. */
    let resolving = false;

    /** Play one clip. A clip that will not play goes through `onRefuse` when it
     *  has one, so the stream's refusal hands off to the buffered voice instead
     *  of ending playback — ending it here is what reopened the mic over a reply
     *  that was still coming, and cut Stark off mid-sentence. */
    const play = (src: string, onRefuse?: (a: HTMLAudioElement) => void) => {
      const a = new Audio(src);
      player.current = a;
      const refuse = () => {
        if (player.current !== a) return;
        if (onRefuse) onRefuse(a);
        else finishPlayback(a);
      };
      a.addEventListener("ended", () => finishPlayback(a));
      a.addEventListener("error", refuse);
      // Autoplay refused or the source unplayable: the words are on screen, so
      // hand back (or fall through) rather than wait for a clip that never starts.
      void a.play().catch(refuse);
      return a;
    };

    /** The stream refused — fetch the whole clip. If it never lands (no voice
     *  provider configured, a dropped request) the mic still comes back, once. */
    const bufferedFallback = (a: HTMLAudioElement) => {
      if (resolving || seq !== speakSeq.current) return;
      resolving = true;
      api
        .speak(text)
        .then(({ audio }) => {
          if (seq !== speakSeq.current) return;
          if (!audio) return finishPlayback(a);
          if (player.current !== a) return;
          a.pause();
          player.current = null;
          speaking.current = true;
          play(audio);
        })
        .catch(() => {
          if (seq === speakSeq.current) finishPlayback(a);
        });
    };

    play(api.speakStreamUrl(text), bufferedFallback);
  };

  return { speak, stopSpeaking, speaking };
}
