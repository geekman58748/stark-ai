import { useState } from "react";
import { FormError } from "@/components/auth/form-error";
import { OrDivider } from "@/components/auth/or-divider";
import { SignInOption } from "@/components/auth/sign-in-option";
import { authClient } from "@/lib/auth/auth-client";
import type { SignInMethod } from "@/lib/auth/types";

export function LogInOptions({
  lastUsed,
  onEmail,
}: {
  lastUsed: SignInMethod | null;
  onEmail: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handleGoogleAuthentication = async () => {
    setError(null);
    setPending(true);
    try {
      await authClient.signInWithGoogle();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach Google.");
      setPending(false);
    }
  };

  return (
    <div className="mt-7 flex flex-col gap-3">
      <SignInOption
        method="google"
        tag={lastUsed === "google" ? "Last used" : undefined}
        disabled={pending}
        onClick={handleGoogleAuthentication}
      >
        {pending ? "Taking you to Google…" : "Continue with Google"}
      </SignInOption>
      <SignInOption
        method="email"
        tag={lastUsed === "email" ? "Last used" : undefined}
        onClick={onEmail}
      >
        Continue with email
      </SignInOption>

      <OrDivider />

      {/* Drawn, not implemented: disabled and labelled so, rather than silently inert. */}
      <SignInOption method="phone" tag="Soon" disabled>
        Continue with phone
      </SignInOption>
      <SignInOption method="telegram" tag="Soon" disabled>
        Continue with Telegram
      </SignInOption>

      <FormError message={error} />
    </div>
  );
}
