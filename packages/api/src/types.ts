// Shapes from docs/API.md (contract v1, frozen). Additive changes only: add fields here,
// never rename or retype them. Money is integer naira; times are ISO 8601 UTC strings.

export type BillKind = "electricity" | "airtime" | "data" | "tv" | "internet" | "water";

export type Bill = {
  id: string;
  kind: BillKind;
  provider: string;
  label: string;
  /** Meter, phone or smartcard number. Never a wallet address. */
  reference: string;
  last_amount_ngn: number | null;
  last_units: number | null;
  last_paid_at: string | null;
  /** Data and TV only: the vendor plan code and its fixed price. */
  plan?: string;
  plan_price_ngn?: number;
  /** Additive: when this bill is supposed to be paid, YYYY-MM-DD. Absent for
   *  meters and lines that do not renew on a schedule. */
  renews_on?: string;
};

/** A bill with a renewal inside the reminder window — the shape of `State.due_soon`. */
export type DueBill = {
  id: string;
  kind: BillKind;
  provider: string;
  label: string;
  /** YYYY-MM-DD. */
  renews_on: string;
  /** 0 is today, negative is overdue. */
  days_until: number;
  price_ngn: number | null;
};

export type State = {
  user_id: string;
  first_name: string;
  currency: "NGN";
  balance_ngn: number;
  cap_ngn: number;
  spent_ngn: number;
  remaining_cap_ngn: number;
  /** null when the user has no electricity bill: hide the block, don't show 0. */
  units_left: number | null;
  /** An estimate from purchase history, not a precise number. */
  days_left: number | null;
  bills: Bill[];
  /** Additive: bills due inside the reminder window, soonest first. */
  due_soon: DueBill[];
  as_of: string;
};

export type ReceiptStatus = "delivered" | "pending" | "failed" | "declined" | "received" | "sent";
export type ReceiptType = "bill" | "autotopup" | "deposit" | "withdrawal";

export type Receipt = {
  id: string;
  /** `"wallet"` for deposits and withdrawals. */
  bill_id: string;
  bill_label: string;
  amount_ngn: number;
  units: number | null;
  /** Electricity only. */
  token: string | null;
  /** Debugging only. Never render. */
  tx_hash?: string | null;
  created_at: string;
  status: ReceiptStatus;
  request_id?: string;
  type: ReceiptType;
  source: string | null;
};

export type Plan = {
  kind: "data" | "tv";
  provider: string;
  service_name: string;
  plan: string;
  /** The vendor's own label. Render as-is. */
  label: string;
  price_ngn: number;
};

export type Limits = {
  monthly_cap_ngn: number;
  per_payment_cap_ngn: number;
  spent_ngn: number;
  remaining_cap_ngn: number;
};

export type Wallet = {
  currency: "NGN";
  balance_ngn: number;
  spent_ngn: number;
  monthly_cap_ngn: number;
  remaining_cap_ngn: number;
  added_this_month_ngn: number;
};

export type WalletMovement = {
  wallet: Wallet;
  entry: Receipt;
};

export type Suggestion = {
  id: string;
  /** Finished copy. Render, don't reassemble. */
  text: string;
  severity: "info" | "warn" | "alert";
  /** Debugging only. */
  reason: string;
};

export type VoiceReply = {
  transcript: string;
  /** true when the wake word was missing: stay completely silent. */
  ignored: boolean;
  reply: string | null;
  token: string | null;
  receipt_id: string | null;
  /** Additive: the reply spoken by the local voice, as a WAV data URL.
   *  null when voice is off (no sidecar configured, or it did not answer). */
  audio?: string | null;
  /** Additive: set when the transcript came from server-side speech-to-text
   *  (an uploaded clip). `"ok"`, or why the clip came back unheard — in which
   *  case `transcript` is empty and `reply` says so. */
  stt?: "ok" | "no_key" | "failed";
};

/** Reply of `POST /v1/speak` — a fetched voice, WAV data URL or null. */
export type SpeakReply = {
  audio: string | null;
};

export type NewBill = {
  kind: BillKind;
  provider: string;
  reference: string;
  label?: string;
  plan?: string;
  /** Additive: when the bill should be paid, YYYY-MM-DD. */
  renews_on?: string;
};

export type BillPatch = {
  label?: string;
  plan?: string;
  /** Additive: set a date (YYYY-MM-DD) or clear it with "". */
  renews_on?: string;
};
/**
 * A single-use code that binds a chat to this account. Returned once, by
 * `POST /v1/link/code`; the server keeps only a hash of it.
 */
export type LinkCode = {
  code: string;
  channel: string;
  /** Seconds until it expires. */
  expires_in: number;
  bot_username: string | null;
  /** `https://t.me/<bot>?start=<code>` — null when the bot has no token. */
  deep_link: string | null;
  user_id?: string;
};

export type LimitsPatch = { monthly_cap_ngn?: number; per_payment_cap_ngn?: number };
export type PaymentInput = { bill_id: string; amount_ngn: number };
/** Test money: there is no payment provider yet, so nothing is collected. */
export type TopUpInput = { amount_ngn: number; request_id?: string };
