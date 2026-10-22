// The browser's own speech recognition, where it exists (Chrome, Edge, Safari). Until the
// backend's speech-to-text is keyed, the transcript goes to /v1/voice as `transcript_hint`.

type RecognitionResult = { 0: { transcript: string }; isFinal: boolean };
type RecognitionEvent = { results: ArrayLike<RecognitionResult> };

export type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};

export function createRecognition(): Recognition | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  };
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  if (!Ctor) return null;
  const r = new Ctor();
  r.lang = "en-NG";
  r.interimResults = true;
  r.continuous = false;
  return r;
}

export function transcriptOf(e: RecognitionEvent) {
  return Array.from(e.results, (r) => r[0].transcript).join(" ");
}
