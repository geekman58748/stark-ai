import { errorCopy } from "@stark/api";
import { FieldError } from "@stark/ui/components/field";

export function BillEditError({ error }: { error: Error }) {
  return <FieldError>{errorCopy(error)}</FieldError>;
}
