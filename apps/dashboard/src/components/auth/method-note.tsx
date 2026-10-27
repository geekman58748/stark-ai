import { MethodIcon } from "@/components/auth/method-icon";
import type { Method } from "@/components/auth/methods";

const COPY: Record<Exclude<Method, "email">, string> = {
  google: "We'll hand you to Google, then straight back here.",
  phone: "We'll text a six-digit code to confirm it's you.",
  telegram: "Continue inside Telegram, where Stark already lives.",
};

export function MethodNote({ method }: { method: Exclude<Method, "email"> }) {
  return (
    <div className="flex flex-1 flex-col justify-center gap-4 rounded-xl border border-line-2 bg-white/2 px-5 py-6">
      <span className="grid size-10 place-items-center rounded-xl bg-brand-wash text-brand-warm">
        <MethodIcon method={method} />
      </span>
      <p className="m-0 max-w-[26ch] text-[14px] leading-relaxed text-fg-2">
        {COPY[method]}
      </p>
    </div>
  );
}
