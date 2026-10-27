import { Card } from "@stark/ui/components/card";
import { formatNaira } from "@stark/utils/format";

export function PlanPriceCard({
  amount,
  provider,
}: {
  amount: number;
  provider: string;
}) {
  return (
    <Card className="flex-row items-center gap-3 p-4">
      <span className="flex flex-1 flex-col">
        <span className="font-medium">{formatNaira(amount)}</span>
        <span className="text-xs text-muted-foreground">
          The {provider} plan price. Plans can’t be part-paid.
        </span>
      </span>
    </Card>
  );
}
