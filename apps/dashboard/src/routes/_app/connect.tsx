import { errorCopy, useLinkCode } from "@stark/api";
import { Button, buttonVariants } from "@stark/ui/components/button";
import { Card } from "@stark/ui/components/card";
import { FieldError } from "@stark/ui/components/field";
import { Icons } from "@stark/ui/components/icons";
import { Spinner } from "@stark/ui/components/spinner";
import { cn } from "@stark/ui/utils/cn";
import { createFileRoute } from "@tanstack/react-router";
import { PageTitle } from "@/components/app-shell";

export const Route = createFileRoute("/_app/connect")({
  head: () => ({ meta: [{ title: "Connect a chat · Stark" }] }),
  component: Connect,
});

/**
 * The app half of identity linking. The bot only trusts a chat bound in
 * `identities.py`, and a code is the only thing that binds it — so this screen
 * is the door: mint one, hand it over, done.
 */
function Connect() {
  const link = useLinkCode();
  const minted = link.data;

  return (
    <>
      <PageTitle>Connect a chat</PageTitle>

      <Card className="gap-3.5">
        <p className="m-0 text-[15px]">
          Stark answers on Telegram with the same brain, the same limits and the same receipts as
          this app — but only for a chat you have linked. A code ties one chat to this account, so
          anyone else who finds the bot can see nothing and spend nothing.
        </p>

        <ol className="m-0 flex list-decimal flex-col gap-1.5 pl-5 text-[13px] text-fg-2">
          <li>Get a code. It is single-use and lasts {minted ? "ten minutes" : "10 minutes"}.</li>
          <li>
            Open Telegram and tap the link, or send <span className="font-mono">link 482913</span>{" "}
            (your own six digits) to the bot.
          </li>
          <li>Then just talk to it: “how much is left”, “pay 5000 for electricity”.</li>
        </ol>

        {minted ? (
          <div
            aria-live="polite"
            className="flex flex-col items-start gap-2 rounded-[14px] bg-surface-3 px-4 py-3.5"
          >
            <span className="text-[13px] text-fg-2">Send this to the bot</span>
            <span className="tabular font-mono text-[28px] leading-none tracking-[0.3em]">
              {minted.code}
            </span>
            <span className="text-[12px] text-muted-foreground">
              Expires in {Math.round(minted.expires_in / 60)} minutes.{" "}
              {minted.deep_link
                ? "One chat only, and /unlink ends it."
                : "Type it by hand — the server has no bot token, so there is no one-tap link."}
            </span>
            {minted.deep_link ? (
              <a
                href={minted.deep_link}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants(), "min-h-10 self-start")}
              >
                <Icons.Telegram size={16} />
                Open @{minted.bot_username} in Telegram
              </a>
            ) : null}
          </div>
        ) : null}

        {link.error ? (
          <FieldError className="text-[13px]">{errorCopy(link.error)}</FieldError>
        ) : null}

        <Button
          onClick={() => link.mutate()}
          disabled={link.isPending}
          className="min-h-10 self-start"
        >
          {link.isPending ? <Spinner /> : <Icons.Telegram size={16} />}
          {minted ? "Get another code" : "Get a code"}
        </Button>
      </Card>

      <Card className="gap-2">
        <span className="font-medium">Why not just trust the chat?</span>
        <p className="m-0 text-[13px] text-fg-2">
          A bot username is public, so any stranger can message it. The code is what makes a chat{" "}
          <em>you</em>: without one, the bot answers link instructions and nothing else — no
          balance, no bills, no payment.
        </p>
      </Card>
    </>
  );
}
