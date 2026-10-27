import { TelegramDeepLink } from "@/components/connect/telegram-deep-link";
import type { LinkCode } from "@stark/api";

export function MintedCode({ minted }: { minted: LinkCode }) {
  return (
    <div
      aria-live="polite"
      className="flex flex-col items-start gap-2 rounded-row bg-surface-3 px-4 py-3.5"
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
        <TelegramDeepLink
          href={minted.deep_link}
          botUsername={minted.bot_username}
        />
      ) : null}
    </div>
  );
}
