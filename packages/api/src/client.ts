import { ApiError } from "./errors";
import type {
  Bill,
  BillKind,
  BillPatch,
  Limits,
  LimitsPatch,
  NewBill,
  PaymentInput,
  Plan,
  Receipt,
  SpeakReply,
  State,
  Suggestion,
  TopUpInput,
  VoiceReply,
  Wallet,
  WalletMovement,
  WithdrawInput,
} from "./types";

let baseUrl = "";

/**
 * Where the backend lives. Leave it empty in the browser during development: Vite proxies
 * `/v1` to the backend, so calls stay same-origin. Set it for deployed builds.
 */
export function setApiBaseUrl(url: string) {
  baseUrl = url.replace(/\/$/, "");
}

/** A recorded clip as base64, chunked so a long utterance cannot blow the stack. */
async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network", "Network request failed");
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      data?.code ?? "unknown",
      data?.message ?? res.statusText,
      data?.detail ?? {},
    );
  }
  return data as T;
}

export const api = {
  state: () => request<State>("GET", "/v1/state"),
  bills: () => request<Bill[]>("GET", "/v1/bills"),
  bill: (id: string) => request<Bill>("GET", `/v1/bills/${encodeURIComponent(id)}`),
  addBill: (input: NewBill) => request<Bill>("POST", "/v1/bills", input),
  updateBill: (id: string, patch: BillPatch) =>
    request<Bill>("PATCH", `/v1/bills/${encodeURIComponent(id)}`, patch),
  deleteBill: (id: string) =>
    request<{ deleted: true; bill_id: string }>("DELETE", `/v1/bills/${encodeURIComponent(id)}`),
  plans: (params: { kind?: Extract<BillKind, "data" | "tv">; provider?: string } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])),
    );
    return request<Plan[]>("GET", `/v1/plans${qs.size ? `?${qs}` : ""}`);
  },
  pay: (input: PaymentInput) => request<Receipt>("POST", "/v1/payments", input),
  activity: () => request<Receipt[]>("GET", "/v1/activity"),
  limits: () => request<Limits>("GET", "/v1/limits"),
  updateLimits: (patch: LimitsPatch) => request<Limits>("PATCH", "/v1/limits", patch),
  wallet: () => request<Wallet>("GET", "/v1/wallet"),
  topUp: (input: TopUpInput) => request<WalletMovement>("POST", "/v1/wallet/topup", input),
  withdraw: (input: WithdrawInput) => request<WalletMovement>("POST", "/v1/wallet/withdraw", input),
  suggestions: () => request<Suggestion[]>("GET", "/v1/suggestions"),
  voice: (transcript_hint: string, opts?: { speak?: boolean }) =>
    request<VoiceReply>("POST", "/v1/voice", {
      transcript_hint,
      // Ask for text only: the dashboard fetches its voice from /v1/speak
      // right after, so reading never waits on synthesis.
      ...(opts?.speak === undefined ? {} : { speak: opts.speak }),
    }),
  /**
   * Real audio: the clip goes up, the server transcribes it (Whisper) and the
   * wake gate runs on what came back — the path for browsers without the Web
   * Speech API. The reply's `stt` field says whether the server heard it.
   */
  voiceAudio: async (audio: Blob, opts?: { speak?: boolean }) =>
    request<VoiceReply>("POST", "/v1/voice", {
      audio: await blobToBase64(audio),
      audio_type: audio.type || "audio/webm",
      ...(opts?.speak === undefined ? {} : { speak: opts.speak }),
    }),
  /** Speak text the client already has — the reply of an answered `/v1/voice`. */
  speak: (text: string) => request<SpeakReply>("POST", "/v1/speak", { text }),
  /**
   * Where the streamed voice lives: `new Audio(api.speakStreamUrl(text))` starts
   * talking on the first bytes instead of waiting for the whole clip to be built.
   * Point an `<audio>` at it and fall back to `speak` if it errors.
   */
  speakStreamUrl: (text: string) => `${baseUrl}/v1/speak/stream?text=${encodeURIComponent(text)}`,
  /** Stub only: restores the seeded demo state. Never call it while someone is demoing. */
  resetDemo: () => request<unknown>("POST", "/v1/_stub/reset", {}),
};
