import type { FundingWay } from "@/lib/wallet/funding-ways";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { listRowClass, RowText } from "@stark/ui/components/list-row";
import { cn } from "@stark/ui/utils/cn";
import { Link } from "@tanstack/react-router";

export function AddMoneyWay({ way }: { way: FundingWay }) {
  const Icon = Icons[way.icon];
  return (
    <Link
      to="/wallet/add"
      search={{ method: way.method }}
      className={cn(
        listRowClass,
        "flex-nowrap gap-3 sm:flex-col sm:items-start sm:gap-2.5 sm:p-4",
      )}
    >
      <IconTile>
        <Icon size={16} />
      </IconTile>
      <RowText
        title={way.title}
        subtitle={way.subtitle}
        className="flex-none sm:flex-none"
      />
    </Link>
  );
}
