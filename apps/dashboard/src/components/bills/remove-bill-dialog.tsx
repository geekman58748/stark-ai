import { type Bill, useDeleteBill } from "@stark/api";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@stark/ui/components/alert-dialog";
import { Button } from "@stark/ui/components/button";
import { Spinner } from "@stark/ui/components/spinner";
import { useNavigate } from "@tanstack/react-router";
import { BillEditError } from "@/components/bills/bill-edit-error";

export function RemoveBillDialog({
  bill,
  open,
  onCancel,
}: {
  bill: Bill;
  open: boolean;
  onCancel: () => void;
}) {
  const remove = useDeleteBill();
  const navigate = useNavigate();
  return (
    <AlertDialog open={open} onOpenChange={(next) => next || onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove {bill.label}?</AlertDialogTitle>
          <AlertDialogDescription>
            Stark won’t be able to pay it any more. Its history stays in your activity.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {remove.error ? <BillEditError error={remove.error} /> : null}
        <AlertDialogFooter>
          <AlertDialogCancel variant="secondary">Keep it</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(bill.id, {
                onSuccess: () => navigate({ to: "/bills" }),
              })
            }
          >
            {remove.isPending ? <Spinner /> : null}
            Remove
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
