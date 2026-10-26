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
