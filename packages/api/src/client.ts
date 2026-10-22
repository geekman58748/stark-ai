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
  voice: (transcript_hint: string) => request<VoiceReply>("POST", "/v1/voice", { transcript_hint }),
  /** Stub only: restores the seeded demo state. Never call it while someone is demoing. */
  resetDemo: () => request<unknown>("POST", "/v1/_stub/reset", {}),
};
