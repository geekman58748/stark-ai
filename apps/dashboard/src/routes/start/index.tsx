import { setAuthToken } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { Eyebrow } from "@stark/ui/components/eyebrow";
import { Icons } from "@stark/ui/components/icons";
import { LogoMark } from "@stark/ui/components/logo";
import { cn } from "@stark/ui/utils/cn";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { signInWithGoogle, signUp } from "@/lib/auth";

export const Route = createFileRoute("/start/")({
  head: () => ({ meta: [{ title: "Sign up · Stark" }] }),
  component: SignUp,
});

/** The card the whole thing sits in — a shade above the canvas it floats on. */
const CARD = "#15171b";
/**
 * The artwork: `apps/dashboard/public/godhand.mp4`, the stop-motion hand passing
 * a wallet to the machine. Re-encoded to H.264 so every browser can play it, and
 * cut so it loops: the blank paper it opens on is trimmed, and the last second
 * dissolves back into the point it resumes at.
 */
const ARTWORK = "/godhand.mp4";
/** The frame to hold when the loop cannot play: the hands, not blank paper. */
const STILL = "/godhand-poster.jpg";

const METHODS = [
  { id: "email", label: "Email", cta: "Create account" },
  { id: "google", label: "Google", cta: "Continue with Google" },
  { id: "phone", label: "Phone", cta: "Continue with phone" },
  { id: "telegram", label: "Telegram", cta: "Continue in Telegram" },
] as const;

type Method = (typeof METHODS)[number]["id"];

function SignUp() {
  const navigate = useNavigate();
  const [method, setMethod] = useState<Method>("email");
  const [details, setDetails] = useState({
    first: "",
    last: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const current = METHODS.find((entry) => entry.id === method) ?? METHODS[0];

  /**
   * Create the account, then go into the app.
   *
   * Email posts to Neon Auth and gets a token back. Google leaves the page instead:
   * the browser returns at `/auth/callback` with a verifier, and that route trades
   * it for the session. Phone and Telegram are drawn, not implemented, and a button
   * that silently does nothing is worse than one that says so — they stay disabled.
   */
  async function submit(event: FormEvent) {
    event.preventDefault();

    if (method === "google") {
      setError(null);
      setPending(true);
      try {
        // Navigates away; it only settles here if the request itself failed.
        await signInWithGoogle();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not reach Google.");
        setPending(false);
      }
      return;
    }

    if (method !== "email") return;
    setError(null);
    setPending(true);
    try {
      const session = await signUp({
        email: details.email,
        password: details.password,
        name: `${details.first} ${details.last}`.trim(),
      });
      setAuthToken(session.token);
      await navigate({ to: "/" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      className="relative grid min-h-dvh w-full lg:grid-cols-[48%_52%]"
      style={{ backgroundColor: CARD }}
    >
      {/* The photograph, and the seam it splits the page on. Large screens only. */}
      <ArtworkPanel />

      <div className="relative flex min-h-dvh flex-col px-6 py-10 sm:px-10 lg:px-14 xl:px-20">
        {/* The panel runs to the window edge; the form keeps a readable measure. */}
        <div className="mx-auto flex w-full max-w-[470px] flex-1 flex-col justify-center">
          <header className="flex items-center justify-between gap-4">
            <Link
              to="/"
              aria-label="Stark home"
              className="flex items-center gap-2 text-fg no-underline hover:text-fg"
            >
              <LogoMark size={26} cutout={CARD} />
              <span className="text-[15px] font-semibold">Stark</span>
            </Link>
            <span className="tabular text-[12px] text-faint">1 of 3</span>
          </header>

          <div className="mt-10 sm:mt-12">
            <Eyebrow>Start for free</Eyebrow>
            <h1 className="m-0 mt-2 font-serif text-[34px] leading-[1.06] font-medium tracking-[-0.015em] text-fg sm:text-[42px]">
              Never run out of light again
              <span className="text-brand">.</span>
            </h1>
            <p className="m-0 mt-2.5 text-[14px] text-fg-2">
              Already have an account?{" "}
              <Link
                to="/login"
                className="font-medium text-brand no-underline hover:text-brand-warm"
              >
                Log in
              </Link>
            </p>
          </div>

          <form className="mt-7 flex flex-col" onSubmit={submit}>
            {/* Pick a method instead of a control that silently rotates through them. */}
            <div
              role="group"
              aria-label="Sign-up method"
              className="grid grid-cols-2 gap-2 sm:grid-cols-4"
            >
              {METHODS.map((entry) => {
                const active = entry.id === method;

                return (
                  <button
                    key={entry.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setMethod(entry.id)}
                    className={cn(
                      "flex h-11 cursor-pointer items-center justify-center gap-2 rounded-xl border px-3 text-[13px] font-medium transition-colors",
                      "focus-visible:border-brand focus-visible:ring-3 focus-visible:ring-brand/25 focus-visible:outline-none",
                      active
                        ? "border-brand/60 bg-brand-wash text-fg"
                        : "border-line-2 bg-white/[0.02] text-fg-2 hover:border-white/20 hover:text-fg",
                    )}
                  >
                    <MethodIcon method={entry.id} />
                    {entry.label}
                  </button>
                );
              })}
            </div>

            {/* Fixed height, so picking another method does not resize the card. */}
            <div className="mt-4 flex min-h-[208px] flex-col gap-3">
              {method === "email" ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label="First name"
                      autoComplete="given-name"
                      placeholder="Tunde"
                      value={details.first}
                      onChange={(value) => setDetails((d) => ({ ...d, first: value }))}
                    />
                    <Field
                      label="Last name"
                      autoComplete="family-name"
                      placeholder="Adebayo"
                      value={details.last}
                      onChange={(value) => setDetails((d) => ({ ...d, last: value }))}
                    />
                  </div>
                  <Field
                    label="Email"
                    type="email"
                    autoComplete="email"
                    placeholder="tunde@example.com"
                    required
                    value={details.email}
                    onChange={(value) => setDetails((d) => ({ ...d, email: value }))}
                  />
                  <PasswordField
                    value={details.password}
                    onChange={(value) => setDetails((d) => ({ ...d, password: value }))}
                  />
                </>
              ) : (
                <MethodNote method={method} />
              )}
            </div>

            {error ? (
              <p role="alert" className="m-0 mt-3 text-[13px] text-destructive">
                {error}
              </p>
            ) : null}

            <Button
              type="submit"
              variant="brand"
              size="lg"
              block
              disabled={pending || (method !== "email" && method !== "google")}
              className="mt-5 h-12 gap-2.5 text-[15px] font-semibold"
            >
              <MethodIcon method={method} />
              {pending
                ? method === "google"
                  ? "Taking you to Google…"
                  : "Creating your account…"
                : current.cta}
            </Button>

            {method !== "email" && method !== "google" ? (
              <p className="m-0 mt-2.5 text-[12px] text-faint">
                {current.label} sign-in is not wired yet. Use email for now.
              </p>
            ) : null}

            <div className="mt-7 flex items-start gap-2.5 border-t border-line pt-6 text-[12.5px] leading-relaxed text-faint">
              <Icons.Lock size={14} className="mt-0.5 shrink-0" />
              <span>Stark can only pay the bills you add, inside limits only you can change.</span>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

/** The icon and glyph a method is recognised by, inline so the CTA can reuse it. */
function MethodIcon({ method }: { method: Method }) {
  if (method === "google") {
    return (
      <span aria-hidden="true" className="text-[13px] font-semibold">
        G
      </span>
    );
  }

  if (method === "phone") {
    return <Icons.Phone size={15} />;
  }

  if (method === "telegram") {
    return <Icons.Telegram size={15} />;
  }

  return <Icons.Mail size={15} />;
}

/** What the other methods show in place of the email form. */
function MethodNote({ method }: { method: Method }) {
  const copy = {
    // Never shown: the email method renders the form instead.
    email: "We'll email you a link to finish setting up.",
    google: "We'll hand you to Google, then straight back here.",
    phone: "We'll text a six-digit code to confirm it's you.",
    telegram: "Continue inside Telegram, where Stark already lives.",
  }[method];

  return (
    <div className="flex flex-1 flex-col justify-center gap-4 rounded-xl border border-line-2 bg-white/[0.02] px-5 py-6">
      <span className="grid size-10 place-items-center rounded-xl bg-brand-wash text-brand-warm">
        <MethodIcon method={method} />
      </span>
      <p className="m-0 max-w-[26ch] text-[14px] leading-relaxed text-fg-2">{copy}</p>
    </div>
  );
}

function Field({
  label,
  type = "text",
  autoComplete,
  placeholder,
  trailing,
  value,
  onChange,
  required,
}: {
  label: string;
  type?: string;
  autoComplete?: string;
  placeholder?: string;
  trailing?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="group flex items-center gap-3 rounded-xl border border-line-2 bg-white/[0.028] px-3.5 py-2.5 transition-colors hover:border-white/15 focus-within:border-brand focus-within:ring-3 focus-within:ring-brand/25">
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-[10px] font-medium tracking-[0.07em] text-faint uppercase transition-colors group-focus-within:text-brand/90">
          {label}
        </span>
        <input
          type={type}
          autoComplete={autoComplete}
          placeholder={placeholder}
          required={required}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full min-w-0 bg-transparent text-[15px] leading-6 text-fg outline-none placeholder:text-faint/70"
        />
      </span>
      {trailing}
    </label>
  );
}

/** The password field with a reveal toggle that actually reveals. */
function PasswordField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [revealed, setRevealed] = useState(false);

  return (
    <Field
      label="Password"
      type={revealed ? "text" : "password"}
      autoComplete="new-password"
      placeholder="At least 8 characters"
      required
      value={value}
      onChange={onChange}
      trailing={
        <button
          type="button"
          onClick={() => setRevealed((was) => !was)}
          aria-pressed={revealed}
          aria-label={revealed ? "Hide password" : "Show password"}
          className="grid size-8 shrink-0 cursor-pointer place-items-center rounded-lg text-faint transition-colors hover:bg-white/5 hover:text-fg-2 focus-visible:ring-2 focus-visible:ring-brand focus-visible:outline-none"
        >
          {revealed ? <Icons.EyeOff size={17} /> : <Icons.Eye size={17} />}
        </button>
      }
    />
  );
}

/**
 * The left column: the loop as a rounded square lying on the panel, so the cream
 * it was shot on reads as a plate on the dark rather than a second half of the
 * page. It runs the height of the column, inset all round, and the label rides
 * inside its top-left corner.
 */
function ArtworkPanel() {
  return (
    <aside className="relative hidden min-h-dvh p-4 lg:flex lg:p-6">
      <div
        className="relative w-full overflow-hidden rounded-[20px]"
        style={{ boxShadow: "0 24px 70px -28px rgb(0 0 0 / 0.85), 0 2px 10px rgb(0 0 0 / 0.45)" }}
      >
        <Artwork />

        <div className="absolute inset-x-0 top-0 z-10 p-4 lg:p-5">
          <span
            className="inline-flex items-center gap-2 rounded-full py-1.5 pr-3.5 pl-3"
            style={{ backgroundColor: "rgb(15 17 21 / 0.86)" }}
          >
            <span className="size-1.5 rounded-full bg-brand-warm" />
            <span className="text-[10px] font-medium tracking-[0.09em] text-white/90 uppercase">
              Prepaid power, handled
            </span>
          </span>
        </div>
      </div>

      {/* The dashed seam the reference splits its card with, hugging the form edge. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 400 700"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 z-10 h-full w-full"
      >
        <path
          d="M392 0 C 372 120, 396 238, 380 358 C 366 468, 394 588, 386 700"
          fill="none"
          stroke="rgb(255 255 255 / 0.12)"
          strokeWidth="1.5"
          strokeDasharray="6 10"
          strokeLinecap="round"
        />
      </svg>
    </aside>
  );
}

/**
 * The loop itself, filling the plate. The plate is taller than the square the
 * clip was shot on, so it covers and crops the outer paper on both sides — the
 * hand at the left and the machine arm at the right both run off frame on
 * purpose, and keeping them whole would mean an empty band top and bottom.
 *
 * It plays as soon as it is on screen, silent, and stops for anyone who asked
 * their OS not to be moved by things.
 */
function Artwork() {
  const [still, setStill] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setStill(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  const frame = "absolute inset-0 block h-full w-full object-cover";

  return still ? (
    <img src={STILL} alt="" aria-hidden="true" className={frame} />
  ) : (
    <video
      src={ARTWORK}
      poster={STILL}
      autoPlay
      muted
      loop
      playsInline
      preload="auto"
      aria-hidden="true"
      tabIndex={-1}
      className={frame}
    />
  );
}
