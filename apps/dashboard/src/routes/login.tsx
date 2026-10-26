import { setAuthToken } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { LogoMark } from "@stark/ui/components/logo";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { signIn } from "@/lib/auth";

/**
 * Sign in.
 *
 * The counterpart to `/start`: same credentials, same provider, one field less. It
 * exists as its own route rather than a mode on the sign-up page because the two
 * do different things to the person using them, and a page that flips between
 * "create" and "enter" hides which one is about to happen.
 */

/** The panel colour, shared with `/start`, so the two screens feel like one flow. */
const CARD = "#15171b";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Log in · Stark" }] }),
  component: LogIn,
});

function LogIn() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const session = await signIn({ email, password });
      setAuthToken(session.token);
      await navigate({ to: "/" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid min-h-dvh w-full place-items-center px-6" style={{ backgroundColor: CARD }}>
      <div className="w-full max-w-[400px]">
        <Link to="/" className="flex items-center gap-2 text-fg no-underline">
          <LogoMark size={26} cutout={CARD} />
          <span className="text-[15px] font-semibold">Stark</span>
        </Link>

        <h1 className="m-0 mt-8 font-serif text-[34px] leading-[1.06] font-medium tracking-[-0.015em] text-fg">
          Welcome back<span className="text-brand">.</span>
        </h1>
        <p className="m-0 mt-2.5 text-[14px] text-fg-2">
          New here?{" "}
          <Link to="/start" className="font-medium text-brand no-underline hover:text-brand-warm">
            Create an account
          </Link>
        </p>

        <form className="mt-7 flex flex-col gap-3" onSubmit={submit}>
          <label className="flex flex-col gap-1 rounded-xl border border-line-2 bg-white/[0.028] px-3.5 py-2.5 transition-colors focus-within:border-brand focus-within:ring-3 focus-within:ring-brand/25">
            <span className="text-[10px] font-medium tracking-[0.07em] text-faint uppercase">
              Email
            </span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="tunde@example.com"
              className="w-full bg-transparent text-[15px] leading-6 text-fg outline-none placeholder:text-faint/70"
            />
          </label>

          <label className="flex flex-col gap-1 rounded-xl border border-line-2 bg-white/[0.028] px-3.5 py-2.5 transition-colors focus-within:border-brand focus-within:ring-3 focus-within:ring-brand/25">
            <span className="text-[10px] font-medium tracking-[0.07em] text-faint uppercase">
              Password
            </span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Your password"
              className="w-full bg-transparent text-[15px] leading-6 text-fg outline-none placeholder:text-faint/70"
            />
          </label>

          {error ? (
            <p role="alert" className="m-0 text-[13px] text-destructive">
              {error}
            </p>
          ) : null}

          <Button
            type="submit"
            variant="brand"
            size="lg"
            block
            disabled={pending}
            className="mt-2 h-12 text-[15px] font-semibold"
          >
            {pending ? "Signing in…" : "Log in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
