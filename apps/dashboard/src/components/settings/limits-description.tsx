import { FieldDescription } from "@stark/ui/components/field";
import { formatNaira } from "@stark/utils/format";

export function LimitsDescription({ spent }: { spent: number }) {
  return (
    <FieldDescription className="text-[13px] text-fg-2">
      If a request goes over, Stark says no and offers the most it can pay instead. Nobody, not even
      Stark, can raise these but you. You’ve spent {formatNaira(spent)} this month.
    </FieldDescription>
  );
}
