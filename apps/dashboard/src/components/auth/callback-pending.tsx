export function CallbackPending({ pending }: { pending: boolean }) {
  return (
    <p className="m-0 mt-2.5 text-[14px] text-fg-2">
      {pending ? "One moment — finishing the handshake with Google." : "Taking you in…"}
    </p>
  );
}
