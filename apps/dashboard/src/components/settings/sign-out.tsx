import { sessionStore } from "@/lib/auth/session-store";
import { api, setAuthToken } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { FieldError } from "@stark/ui/components/field";
import { Spinner } from "@stark/ui/components/spinner";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

export function SignOut() {
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSignOut = async () => {
    setPending(true);
    setError(null);
    try {
      // Server first: forgetting the token locally would leave a live session behind.
      await api.logout();
    } catch {
      // A dead session is exactly what we are trying to end, so keep going.
    }
    try {
      sessionStore.forget();
      setAuthToken(null);
      await navigate({ to: "/login" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign out.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        variant="secondary"
        onClick={handleSignOut}
        disabled={pending}
        className="min-h-10 self-start"
      >
        {pending ? <Spinner /> : null}
        Log out
      </Button>
      {error ? <FieldError className="text-[13px]">{error}</FieldError> : null}
    </div>
  );
}
