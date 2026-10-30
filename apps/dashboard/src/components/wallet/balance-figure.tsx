import { formatNaira } from "@stark/utils/format";

export function BalanceFigure({ amount, note }: { amount: number; note: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-2.5">
      <span className="font-serif text-5xl leading-none">{formatNaira(amount)}</span>
      <span className="text-xs text-muted-foreground">{note}</span>
    </div>
  );
}
