import {
  api,
  errorCopy,
  limitsQuery,
  setAuthToken,
  useResetDemo,
  useUpdateLimits,
} from "@stark/api";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@stark/ui/components/alert-dialog";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { FieldDescription, FieldError, FieldGroup } from "@stark/ui/components/field";
import { Icons } from "@stark/ui/components/icons";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { PageTitle } from "@/components/app-shell";
import { forgetToken } from "@/lib/auth";

export const Route = createFileRoute("/_app/settings")({
  loader: ({ context }) => context.queryClient.query({ ...limitsQuery(), staleTime: "static" }),
  head: () => ({ meta: [{ title: "Settings · Stark" }] }),
  component: Settings,
});

function Settings() {
  const { data: limits } = useSuspenseQuery(limitsQuery());
  const [monthly, setMonthly] = useState(limits.monthly_cap_ngn);
  const [per, setPer] = useState(limits.per_payment_cap_ngn);
  const update = useUpdateLimits();
  const dirty = monthly !== limits.monthly_cap_ngn || per !== limits.per_payment_cap_ngn;
  const invalid = monthly <= 0 || per <= 0 || per > monthly;

  return (
    <>
      <PageTitle>Settings</PageTitle>

      <SectionHeading>Spending limits</SectionHeading>
      <Card>
        <form
          className="m-0"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate({ monthly_cap_ngn: monthly, per_payment_cap_ngn: per });
          }}
        >
          <FieldGroup>
            <AmountField
              label="Most Stark can spend in a month"
              value={monthly}
              onChange={(v) => {
                update.reset();
                setMonthly(v);
              }}
              presets={[20000, 30000, 50000, 100000]}
            />
            <AmountField
              label="Most it can spend at once"
              value={per}
              onChange={(v) => {
                update.reset();
                setPer(v);
              }}
              presets={[5000, 10000, 20000]}
              error={
                per > monthly ? "A single payment can’t be more than the monthly limit." : undefined
              }
            />
            <FieldDescription className="text-[13px] text-fg-2">
              If a request goes over, Stark says no and offers the most it can pay instead. Nobody,
              not even Stark, can raise these but you. You’ve spent {formatNaira(limits.spent_ngn)}{" "}
              this month.
            </FieldDescription>
            {update.error ? (
              <FieldError className="text-[13px]">{errorCopy(update.error)}</FieldError>
            ) : null}
            {update.isSuccess && !dirty ? (
              <p aria-live="polite" className="m-0 flex items-center gap-2 text-[13px] text-fg-2">
                <Icons.Check size={16} className="text-brand-warm" />
                Saved. Stark uses the new limits from its next payment.
              </p>
            ) : null}
            {dirty ? (
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={invalid || update.isPending}>
                  {update.isPending ? <Spinner /> : null}
                  Save {formatNaira(monthly)} a month, {formatNaira(per)} at once
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setMonthly(limits.monthly_cap_ngn);
                    setPer(limits.per_payment_cap_ngn);
                  }}
                >
                  Undo
                </Button>
              </div>
            ) : null}
          </FieldGroup>
        </form>
      </Card>

      <SectionHeading>This account</SectionHeading>
      <Card className="gap-2">
        <span className="font-medium">Signed in</span>
        <p className="m-0 text-[13px] text-fg-2">
          Stark only ever pays from the wallet in this account. Logging out ends the session on the
          server, not just in this tab.
        </p>
        <SignOut />
      </Card>

      <SectionHeading>How Stark listens</SectionHeading>
      <Card className="gap-2">
        <span className="font-medium">Telegram and the wall phone</span>
        <p className="m-0 text-[13px] text-fg-2">
          Voice notes only count when they include the word “Stark”, so everyday talk in the room
          never triggers a payment.
        </p>
        <Button
          variant="secondary"
          nativeButton={false}
          render={<Link to="/connect" />}
          className="min-h-10 self-start"
        >
          <Icons.Telegram size={16} />
          Connect a chat
        </Button>
      </Card>

      {import.meta.env.DEV ? <ResetDemo /> : null}
    </>
  );
}

function SignOut() {
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function leave() {
    setPending(true);
    setError(null);
    try {
      // Server first: forgetting the token locally would leave a live session behind.
      await api.logout();
    } catch {
      // A dead session is exactly what we are trying to end, so keep going.
    }
    try {
      forgetToken();
      setAuthToken(null);
      await navigate({ to: "/login" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign out.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" onClick={leave} disabled={pending} className="min-h-10 self-start">
        {pending ? <Spinner /> : null}
        Log out
      </Button>
      {error ? <FieldError className="text-[13px]">{error}</FieldError> : null}
    </div>
  );
}

function ResetDemo() {
  const reset = useResetDemo();
  const [open, setOpen] = useState(false);
  return (
    <Card className="flex-row flex-wrap items-center gap-3">
      <span className="flex flex-[1_1_240px] flex-col">
        <span className="font-medium">Reset the demo</span>
        <span className="text-[13px] text-muted-foreground">
          Puts the seeded bills, balance and history back. Bills you added are removed.
        </span>
      </span>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger render={<Button variant="secondary" />}>Reset</AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset the demo?</AlertDialogTitle>
            <AlertDialogDescription>
              The seeded bills, balance and history come back. Bills you added are removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {reset.error ? (
            <FieldError className="text-[13px]">{errorCopy(reset.error)}</FieldError>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel variant="secondary">Keep my data</AlertDialogCancel>
            <Button
              disabled={reset.isPending}
              onClick={() => reset.mutate(undefined, { onSuccess: () => setOpen(false) })}
            >
              {reset.isPending ? <Spinner /> : null}
              Yes, reset
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
