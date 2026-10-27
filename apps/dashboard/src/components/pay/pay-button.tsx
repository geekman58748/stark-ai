import { Button } from "@stark/ui/components/button";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";

export function PayButton({
  amount,
  pending,
  disabled,
  onClick,
}: {
  amount: number;
  pending: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Button size="lg" block disabled={disabled} onClick={onClick}>
      {pending ? <Spinner /> : null}
      {pending ? "Paying…" : `Pay ${formatNaira(amount)}`}
    </Button>
  );
}
