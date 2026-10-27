import type { Receipt } from "@stark/api";
import { Stat, StatGrid } from "@stark/ui/components/stat";

export function ReceiptStats({ receipt }: { receipt: Receipt }) {
  return (
    <StatGrid>
      {receipt.source ? <Stat label="Asked via">{receipt.source}</Stat> : null}
      {receipt.units ? <Stat label="Units">{receipt.units} kWh</Stat> : null}
      <Stat label="Receipt ID">
        <span className="tabular">{receipt.id.toUpperCase()}</span>
      </Stat>
    </StatGrid>
  );
}
