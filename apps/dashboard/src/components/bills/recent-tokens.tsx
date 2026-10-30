import type { Receipt } from "@stark/api";
import { RowList } from "@stark/ui/components/list-row";
import { SectionHeading } from "@stark/ui/components/section-heading";
import { formatNaira, formatShortDate } from "@stark/utils/format";
import { TokenLine } from "@/components/pay/token-line";

export function RecentTokens({ history }: { history: Receipt[] }) {
  const withTokens = history.filter((r) => r.status === "delivered" && r.token).slice(0, 3);
  if (!withTokens.length) return null;
  return (
    <>
      <SectionHeading action={withTokens.length}>Recent tokens</SectionHeading>
      <RowList>
        {withTokens.map((r) => (
          <TokenLine
            key={r.id}
            token={r.token!}
            note={`${formatShortDate(r.created_at)} · ${formatNaira(r.amount_ngn)}`}
          />
        ))}
      </RowList>
    </>
  );
}
