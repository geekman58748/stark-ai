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

  return { speak, stopSpeaking, speaking };
}
