import { errorCopy, useWithdraw } from "@stark/api";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button } from "@stark/ui/components/button";
import { FieldError } from "@stark/ui/components/field";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";
import { requestId } from "@stark/utils/id";
import { type SubmitEvent, useMemo, useState } from "react";

export function WithdrawForm({
  max,
  onDone,
}: {
  max: number;
  onDone: () => void;
}) {
  const [amount, setAmount] = useState(Math.min(10000, max));
  const withdraw = useWithdraw();
  const key = useMemo(() => requestId("wd"), [amount]);

  const handleWithdraw = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    withdraw.mutate(
      { amount_ngn: amount, request_id: key },
      { onSuccess: onDone },
    );
  };

  return (
    <form
      className="m-0 flex flex-col gap-3 rounded-row border border-line bg-canvas p-4"
      onSubmit={handleWithdraw}
    >
      <AmountField
        label="Send to your bank"
        value={amount}
        onChange={setAmount}
        presets={[5000, 10000, max].filter(
          (v, i, a) => v > 0 && v <= max && a.indexOf(v) === i,
        )}
      />
      {withdraw.error ? (
        <FieldError className="text-[13px]">
          {errorCopy(withdraw.error)}
        </FieldError>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={amount <= 0 || withdraw.isPending}>
          {withdraw.isPending ? <Spinner /> : null}
          {withdraw.isPending ? "Sending…" : `Withdraw ${formatNaira(amount)}`}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
