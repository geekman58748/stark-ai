import { AddMoneyWay } from "@/components/wallet/add-money-way";
import { FundingWays } from "@/lib/wallet/funding-ways";

export function AddMoneyWays() {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {FundingWays.all.map((way) => (
        <AddMoneyWay key={way.method} way={way} />
      ))}
    </div>
  );
}
