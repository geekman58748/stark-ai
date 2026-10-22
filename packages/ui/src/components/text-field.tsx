import { Field, FieldDescription, FieldLabel } from "@stark/ui/components/field";
import { Input } from "@stark/ui/components/input";
import { type ComponentProps, useId } from "react";

/** A labelled text input: shadcn Field + Input. */
export function TextField({
  label,
  hint,
  className,
  id,
  ...props
}: ComponentProps<typeof Input> & { label: string; hint?: string }) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <Field className={className}>
      <FieldLabel htmlFor={inputId} className="text-fg-2 font-normal">
        {label}
      </FieldLabel>
      <Input id={inputId} {...props} />
      {hint ? <FieldDescription className="text-xs">{hint}</FieldDescription> : null}
    </Field>
  );
}
