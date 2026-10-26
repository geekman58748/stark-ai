/**
 * Accounts, straight from the browser to Neon Auth.
 *
 * Neon Auth is Better Auth under the hood, served at `VITE_NEON_AUTH_URL`
 * (`https://<endpoint>/<database>/auth`). The browser talks to it directly — there
 * is no password anywhere in this repo, and no route of ours that accepts one.
 *
 * What we keep is the **session token** it hands back. That token goes on every
 * `/v1` call as a bearer header, and the backend resolves it against the provider's
 * `neon_auth.session` row (see `apps/backend/auth.py`). Which means:
 *
 *  - signing out must delete that row, not just forget the token locally, or a
 *    captured token would outlive the session it belonged to;
 *  - a token in `localStorage` is a real credential — the trade for a SPA with no
 *    server-rendered session, and the reason `signOut` calls the API first.
 */

const STORAGE_KEY = "stark.session";

export type AuthUser = {
  id: string;
  email: string;
  name?: string | null;
  emailVerified?: boolean;
};

export type Session = { token: string; user: AuthUser };

/** The provider's base URL, or a clear reason the app cannot sign anyone in. */
function authBase(): string {
  const url = import.meta.env.VITE_NEON_AUTH_URL;
  if (!url) {
    throw new Error("Sign-in is not configured: set VITE_NEON_AUTH_URL (see .env.example).");
  }
  return url.replace(/\/$/, "");
}

async function call<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${authBase()}${path}`, {
    method: "POST",
    // Neon keeps the OAuth round-trip's state in a cookie on its own origin, so the
    // request has to be allowed to carry it. It is `SameSite=None; Partitioned`,
    // which is exactly what makes that possible from this origin.
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  const data = (await res.json().catch(() => null)) as
    | (T & { message?: string; code?: string })
    | null;

  if (!res.ok) {
    // The provider's messages are already user-facing ("Invalid email or password"),
    // so they are shown as-is rather than reworded into something vaguer.
    throw new Error(data?.message ?? `Could not reach the sign-in service (${res.status}).`);
  }
  if (!data) throw new Error("The sign-in service returned nothing.");
  return data;
}

function store(session: Session): Session {
  try {
    window.localStorage.setItem(STORAGE_KEY, session.token);
  } catch {
    // Private mode with storage disabled: the session still works for this tab,
    // it just will not survive a reload.
  }
  return session;
}

/** The token from a previous visit, if there is one. */
export function storedToken(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function forgetToken(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to forget.
  }
}

export async function signUp(input: {
  email: string;
  password: string;
  name?: string;
}): Promise<Session> {
  const session = await call<Session>("/sign-up/email", {
    email: input.email.trim(),
    password: input.password,
    name: input.name?.trim() || input.email.split("@")[0],
  });
  return store(session);
}

export async function signIn(input: { email: string; password: string }): Promise<Session> {
  const session = await call<Session>("/sign-in/email", {
    email: input.email.trim(),
    password: input.password,
  });
  return store(session);
}

/** The query parameter Neon appends on the way back from an OAuth provider. */
const VERIFIER_PARAM = "neon_auth_session_verifier";

/** Where the browser returns to after Google has had its say. */
const CALLBACK_PATH = "/auth/callback";

/**
 * Hand the browser to Google.
 *
 * This one does not return a session — it navigates away and only comes back at
 * `/auth/callback`. It settles if the request itself failed, which is why callers
 * keep their pending state until it does.
 */
export async function signInWithGoogle(): Promise<void> {
  const callbackURL = `${window.location.origin}${CALLBACK_PATH}`;
  const data = await call<{ url?: string }>("/sign-in/social", {
    provider: "google",
    callbackURL,
    // A refusal from Google comes back to a URL this page recognises.
    errorCallbackURL: `${callbackURL}?error=1`,
  });
  if (!data?.url) throw new Error("Google sign-in did not return an address to go to.");
  window.location.assign(data.url);
}

/**
 * Trade the verifier Neon put on the callback URL for a real session.
 *
 * The cookie Neon sets is partitioned to its own origin, so it is deliberately not
 * the thing relied on here: the verifier is single-use and arrives on the URL. The
 * `/get-session` answer carries the same token the email flow stores, which is the
 * token `apps/backend/auth.py` looks up in `neon_auth.session`.
 */
export async function sessionFromCallback(search: string): Promise<Session | null> {
  const verifier = new URLSearchParams(search).get(VERIFIER_PARAM);
  if (!verifier) return null;

  const res = await fetch(
    `${authBase()}/get-session?${VERIFIER_PARAM}=${encodeURIComponent(verifier)}`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(`Could not finish signing in (${res.status}).`);

  const data = (await res.json().catch(() => null)) as {
    session?: { token?: string } | null;
    user?: AuthUser;
  } | null;
  const token = data?.session?.token;
  if (!token || !data?.user) return null;

  return store({ token, user: data.user });
}
