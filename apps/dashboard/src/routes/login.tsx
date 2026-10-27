import { AuthIntro } from "@/components/auth/auth-intro";
import { AuthScreen } from "@/components/auth/auth-screen";
import { EmailLogInForm } from "@/components/auth/email-log-in-form";
import { LogInOptions } from "@/components/auth/log-in-options";
import { sessionStore } from "@/lib/auth/session-store";
import type { SignInMethod } from "@/lib/auth/types";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

/**
 * Sign in: the counterpart to `/start`, on the same screen. It opens on one
 * button per way in; email swaps the list for its fields, with a way back.
 */
export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Log in · Stark" }] }),
  component: LogIn,
});

function LogIn() {
  const [withEmail, setWithEmail] = useState(false);
  // Read after mount: storage is the browser's, and the first render must match the server's.
  const [lastUsed, setLastUsed] = useState<SignInMethod | null>(null);
  useEffect(() => setLastUsed(sessionStore.lastMethod()), []);

  return (
    <AuthScreen>
      <AuthIntro
        eyebrow="Log in"
        title="Welcome back"
        prompt="New here?"
        link={{ to: "/start", label: "Create an account" }}
      />
      {withEmail ? (
        <EmailLogInForm onBack={() => setWithEmail(false)} />
      ) : (
        <LogInOptions lastUsed={lastUsed} onEmail={() => setWithEmail(true)} />
      )}
    </AuthScreen>
  );
}
