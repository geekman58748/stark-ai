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
  onerror: ((e: { error?: string }) => void) | null;
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

/**
 * A dismissal, not a question. Anchored on purpose: "stop paying my DStv" is an
 * instruction to Stark, "stop listening" is not — a rule that fires on a
 * sentence merely *containing* "stop" would hang up mid-command.
 *
 * Anchoring has a cost, measured 2026-10-24: "I think that's enough goodbye I
 * don't need your help anymore" reached the server and the mic stayed awake,
 * because a dismissal written *into* a sentence can never match a rule that
 * owns the whole utterance. The short risky words (`sleep`, a bare `stop`)
 * stay anchored; everything unambiguous enough to stand alone is also looked
 * for anywhere by `SLEEP_ANYWHERE` below.
 */
const SLEEP_INTENT = new RegExp(
  "^(?:(?:hey|hi|ok|okay|yo|so|no|thanks|thank\\s+you)[,\\s]+)*" +
    "(?:stark[,\\s]+)?" +
    "(?:you\\s+can\\s+)?" +
    "(?:" +
    // Contractions the way recognizers write them both ways: "that's"/"thats"/
    // "that is", and the curly apostrophe Safari returns.
    "go\\s+to\\s+sleep|stop\\s+listening|sleep" +
    "|(?:that\\s*['\u2019]?s|that\\s+is)\\s+(?:all|it)" +
    "|goodbye|bye|(?:i\\s*['\u2019]?m|i\\s+am)\\s+done" +
    ")" +
    "(?:[,\\s]+(?:now|please|thanks|thank\\s+you))*[.!]*$",
  "i",
);

/**
 * A dismissal buried in a longer sentence. Each phrase here means the same
 * thing wherever it sits, and none of them is a bill, an amount or a command:
 * "stop paying my DStv", "how much is left" and "don't need help with the
 * light bill" all contain none of these, so they stay awake.
 */
const SLEEP_ANYWHERE = new RegExp(
  "\\b(?:" +
    "go\\s+to\\s+sleep|stop\\s+listening" +
    "|(?:that\\s*['\u2019]?s|that\\s+is|that\\s+will\\s+be)\\s+(?:all|it|enough)" +
    "|good\\s*bye|goodbye|bye" +
    "|(?:i\\s*['\u2019]?m|i\\s+am)\\s+done" +
    "|(?:i\\s*['\u2019]?ve|i\\s+have)\\s+had\\s+enough" +
    "|(?:i\\s+)?(?:don['\u2019]?t|do\\s+not)\\s+need\\s+(?:your\\s+)?help" +
    ")\\b",
  "i",
);

export function isSleepIntent(text: string) {
  const said = text.trim().replace(/\s+/g, " ");
  return SLEEP_INTENT.test(said) || SLEEP_ANYWHERE.test(said);
}
