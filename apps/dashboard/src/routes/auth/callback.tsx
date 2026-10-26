import { setAuthToken } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { LogoMark } from "@stark/ui/components/logo";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { sessionFromCallback } from "@/lib/auth";

/**
 * Where the browser lands after Google.
 *
 * Neon finishes the OAuth exchange on its own origin and redirects here with a
 * single-use verifier in the query string. This page spends that verifier on
 * `/get-session`, keeps the token the app already knows how to use, and leaves —
 * so the URL holding the verifier is never the one left in the address bar.
 */

/** The panel colour, shared with `/start` and `/login`, so the flow feels like one. */
const CARD = "#15171b";

export const Route = createFileRoute("/auth/callback")({
  head: () => ({ meta: [{ title: "Signing in · Stark" }] }),
  component: AuthCallback,
});

function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);
  // The verifier is single-use, and Strict Mode mounts effects twice.
  const spent = useRef(false);

  useEffect(() => {
    if (spent.current) return;
    spent.current = true;

    const search = window.location.search;
    if (new URLSearchParams(search).get("error")) {
      setPending(false);
      setError("Google did not finish signing you in. Try again, or use your email.");
      return;
    }

    sessionFromCallback(search)
      .then((session) => {
        if (!session) {
          setError("That sign-in link has expired. Start again and it will work.");
          setPending(false);
          return;
        }
        setAuthToken(session.token);
        // The verifier is spent: take it out of the address bar and the history.
        window.history.replaceState({}, "", window.location.pathname);
        return navigate({ to: "/" });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not finish signing in."))
      .finally(() => setPending(false));
  }, [navigate]);

  return (
    <div
      className="grid min-h-dvh w-full place-items-center px-6"
      style={{ backgroundColor: CARD }}
    >
      <div className="w-full max-w-[400px]">
        <Link to="/" className="flex items-center gap-2 text-fg no-underline">
          <LogoMark size={26} cutout={CARD} />
          <span className="text-[15px] font-semibold">Stark</span>
        </Link>

        <h1 className="m-0 mt-8 font-serif text-[34px] leading-[1.06] font-medium tracking-[-0.015em] text-fg">
          {error ? "That did not go through" : "Signing you in"}
          <span className="text-brand">.</span>
        </h1>

        {error ? (
          <>
            <p role="alert" className="m-0 mt-2.5 text-[14px] leading-relaxed text-fg-2">
              {error}
            </p>
            <Button
              type="button"
              variant="brand"
              size="lg"
              block
              className="mt-6 h-12 text-[15px] font-semibold"
              onClick={() => navigate({ to: "/start" })}
            >
              Start again
            </Button>
            <p className="m-0 mt-3 text-[13px] text-faint">
              Or{" "}
              <Link
                to="/login"
                className="font-medium text-brand no-underline hover:text-brand-warm"
              >
                log in with your email
              </Link>
              .
            </p>
          </>
        ) : (
          <p className="m-0 mt-2.5 text-[14px] text-fg-2">
            {pending ? "One moment — finishing the handshake with Google." : "Taking you in…"}
          </p>
        )}
      </div>
    </div>
  );
}
