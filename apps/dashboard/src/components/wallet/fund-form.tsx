import { FundMethodCard } from "@/components/wallet/fund-method-card";
import { FundMethodPicker } from "@/components/wallet/fund-method-picker";
import { type FundMethod, FundMethods } from "@/lib/wallet/fund-methods";
import { errorCopy, useTopUp } from "@stark/api";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button } from "@stark/ui/components/button";
import { FieldError } from "@stark/ui/components/field";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";
import { requestId } from "@stark/utils/id";
import { useMemo, useState } from "react";

export function FundForm({
  initialMethod = "bank",
  onDone,
}: {
  initialMethod?: FundMethod;
  onDone: () => void;
}) {
  const [amount, setAmount] = useState(20000);
  const [method, setMethod] = useState<FundMethod>(initialMethod);
  const topUp = useTopUp();

  const key = useMemo(() => requestId("dep"), [amount, method]);
  const current = FundMethods.get(method);

  const handleFundWallet = () =>
    topUp.mutate(
      { amount_ngn: amount, request_id: key, source: current.source },
      { onSuccess: onDone },
    );

  return (
    <div className="flex flex-col gap-6">
      <AmountField
        label="Amount"
        value={amount}
        onChange={setAmount}
        presets={[10000, 20000, 50000]}
      />
      <FundMethodPicker value={method} onValueChange={setMethod} />
      <FundMethodCard name={current.name} detail={current.detail} />
      {topUp.error ? (
        <FieldError className="text-[13px]">
          {errorCopy(topUp.error)}
        </FieldError>
      ) : null}
      <Button
        size="lg"
        block
        disabled={amount <= 0 || topUp.isPending}
        onClick={handleFundWallet}
      >
        {topUp.isPending ? <Spinner /> : null}
        {topUp.isPending ? "Adding…" : `Add ${formatNaira(amount)}`}
      </Button>
    </div>
  );
}
