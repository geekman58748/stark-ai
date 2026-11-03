import type { CryptoAsset } from "@stark/api/types";
import { Field, FieldLabel } from "@stark/ui/components/field";
import { NativeSelect, NativeSelectOption } from "@stark/ui/components/native-select";
import { useId } from "react";

export function CryptoAssetSelect({
  label,
  placeholder,
  assets,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  assets: CryptoAsset[];
  value: string;
  onChange: (assetId: string) => void;
}) {
  const id = useId();
  return (
    <Field className="gap-2.5">
      <FieldLabel htmlFor={id} className="font-normal text-fg-2">
        {label}
      </FieldLabel>
      <NativeSelect
        id={id}
        className="w-full"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <NativeSelectOption value="" disabled>
          {placeholder}
        </NativeSelectOption>
        {assets.map((asset) => (
          <NativeSelectOption key={asset.asset_id} value={asset.asset_id}>
            {asset.symbol} on {asset.chain}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </Field>
  );
}
