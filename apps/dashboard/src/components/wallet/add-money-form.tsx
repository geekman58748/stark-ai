import { errorCopy } from "@stark/api/errors";
import { useStartDeposit } from "@stark/api/mutations";
import { cryptoAssetsQuery } from "@stark/api/queries";
import type { Deposit, FundingMethods } from "@stark/api/types";
import { AmountField } from "@stark/ui/components/amount-field";
import { Button } from "@stark/ui/components/button";
import { FieldError } from "@stark/ui/components/field";
import { PillTabs } from "@stark/ui/components/pill-tabs";
import { Spinner } from "@stark/ui/components/spinner";
import { formatNaira } from "@stark/utils/format";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CryptoAssetSelect } from "@/components/wallet/crypto-asset-select";
import { FundForm } from "@/components/wallet/fund-form";

type Method = "bank" | "crypto" | "test";

const LABELS: Record<Method, string> = {
  bank: "Bank or card",
  crypto: "Crypto",
  test: "Test money",
};

/** Pick how to pay and how much. Starting a deposit moves nothing until it settles. */
export function AddMoneyForm({
  methods,
  onStarted,
  onTestMoneyAdded,
}: {
  methods: FundingMethods;
  onStarted: (deposit: Deposit) => void;
  onTestMoneyAdded: () => void;
}) {
  const offered = (["bank", "crypto", "test"] as const).filter((m) =>
    m === "test" ? methods.test_money : methods[m],
  );
  const [method, setMethod] = useState<Method>(offered[0] ?? "test");
  const [amount, setAmount] = useState(20000);
  const [assetId, setAssetId] = useState("");
  const assets = useQuery({ ...cryptoAssetsQuery(), enabled: method === "crypto" });
  const start = useStartDeposit();

  if (offered.length === 0) {
    return <p className="m-0 text-fg-2">Adding money isn’t switched on here yet.</p>;
  }

  const handleStart = () => {
    const input =
      method === "crypto"
        ? { method, amount_ngn: amount, asset_id: assetId }
        : { method: "bank" as const, amount_ngn: amount };
    start.mutate(input, { onSuccess: onStarted });
  };

  return (
    <div className="flex flex-col gap-6">
      {offered.length > 1 ? (
        <PillTabs
          label="How you’re paying"
          tabs={offered.map((value) => ({ value, label: LABELS[value] }))}
          value={method}
          onChange={setMethod}
        />
      ) : null}

      {method === "test" ? (
        <FundForm onDone={onTestMoneyAdded} />
      ) : (
        <>
          <AmountField
            label="Amount"
            value={amount}
            onChange={setAmount}
            presets={[10000, 20000, 50000]}
          />
          {method === "crypto" ? (
            <CryptoAssetSelect
              label="Pay with"
              placeholder="Choose what you hold"
              assets={assets.data ?? []}
              value={assetId}
              onChange={setAssetId}
            />
          ) : null}
          {start.error ? (
            <FieldError className="text-[13px]">{errorCopy(start.error)}</FieldError>
          ) : null}
          <Button
            size="lg"
            block
            disabled={amount < 100 || start.isPending || (method === "crypto" && !assetId)}
            onClick={handleStart}
          >
            {start.isPending ? <Spinner /> : null}
            {method === "bank"
              ? `Pay ${formatNaira(amount)}`
              : `Get a price for ${formatNaira(amount)}`}
          </Button>
        </>
      )}
    </div>
  );
}
