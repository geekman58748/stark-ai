import { errorCopy } from "@stark/api/errors";
import { FieldError } from "@stark/ui/components/field";

export function BillEditError({ error }: { error: Error }) {
  return <FieldError>{errorCopy(error)}</FieldError>;
}
