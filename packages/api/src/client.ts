import { ApiError } from "./errors";
import type {
  Bill,
  BillKind,
  BillPatch,
  Limits,
  LimitsPatch,
  LinkCode,
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
let authToken: string | null = null;

/**
 * Where the backend lives. Leave it empty in the browser during development: Vite proxies
 * `/v1` to the backend, so calls stay same-origin. Set it for deployed builds.
 */
export function setApiBaseUrl(url: string) {
  baseUrl = url.replace(/\/$/, "");
}

/**
 * The Neon Auth session token, sent as `Authorization: Bearer`.
 *
 * Set once at boot from storage, and again after sign-in or sign-out. Kept here
 * rather than read from storage per request so a signed-out tab cannot keep
 * working because localStorage still had a token in it.
 */
export function setAuthToken(token: string | null) {
  authToken = token;
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
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    res = await fetch(`${baseUrl}${path}`, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
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
  /**
   * Ends the session server-side as well as locally: the provider's session row
   * is deleted, so the token this tab was holding cannot be replayed.
   */
  logout: () => request<{ logged_out: true }>("POST", "/v1/auth/logout", {}),
  /** A fresh single-use code for linking a chat. Every call mints a new one. */
  linkCode: () => request<LinkCode>("POST", "/v1/link/code", {}),
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
