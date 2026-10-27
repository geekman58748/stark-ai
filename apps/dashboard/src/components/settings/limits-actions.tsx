import { Button } from "@stark/ui/components/button";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";

export function LimitsActions({
  monthly,
  per,
  invalid,
  pending,
  onUndo,
}: {
  monthly: number;
  per: number;
  invalid: boolean;
  pending: boolean;
  onUndo: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button type="submit" disabled={invalid || pending}>
        {pending ? <Spinner /> : null}
        Save {formatNaira(monthly)} a month, {formatNaira(per)} at once
      </Button>
      <Button type="button" variant="ghost" onClick={onUndo}>
        Undo
      </Button>
    </div>
  );
}
