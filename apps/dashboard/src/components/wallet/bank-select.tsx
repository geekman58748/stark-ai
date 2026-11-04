import type { Bank } from "@stark/api/types";
import { Field, FieldLabel } from "@stark/ui/components/field";
import { NativeSelect, NativeSelectOption } from "@stark/ui/components/native-select";
import { useId } from "react";

export function BankSelect({
  banks,
  value,
  onChange,
}: {
  banks: Bank[];
  value: string;
  onChange: (code: string) => void;
}) {
  const id = useId();
  return (
    <Field className="gap-2.5">
      <FieldLabel htmlFor={id} className="font-normal text-fg-2">
        Bank
      </FieldLabel>
      <NativeSelect
        id={id}
        className="w-full"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <NativeSelectOption value="" disabled>
          Choose your bank
        </NativeSelectOption>
        {banks.map((bank) => (
          <NativeSelectOption key={bank.code} value={bank.code}>
            {bank.name}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </Field>
  );
}
