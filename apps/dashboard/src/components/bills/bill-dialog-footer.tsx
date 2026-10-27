import { Button } from "@stark/ui/components/button";
import { DialogClose, DialogFooter } from "@stark/ui/components/dialog";
import { Spinner } from "@stark/ui/components/spinner";
import type { ReactNode } from "react";

export function BillDialogFooter({
  disabled,
  pending,
  children,
}: {
  disabled: boolean;
  pending: boolean;
  children: ReactNode;
}) {
  return (
    <DialogFooter>
      <DialogClose render={<Button variant="ghost" />}>Cancel</DialogClose>
      <Button type="submit" disabled={disabled}>
        {pending ? <Spinner /> : null}
        {children}
      </Button>
    </DialogFooter>
  );
}
