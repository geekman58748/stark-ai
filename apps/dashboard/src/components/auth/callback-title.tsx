export function CallbackTitle({ error }: { error: string | null }) {
  return (
    <h1 className="m-0 mt-8 font-serif text-[34px] leading-[1.06] font-medium tracking-[-0.015em] text-fg">
      {error ? "That did not go through" : "Signing you in"}
      <span className="text-brand">.</span>
    </h1>
  );
}
