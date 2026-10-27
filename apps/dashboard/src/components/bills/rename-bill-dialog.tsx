import { RenameBillForm } from "@/components/bills/rename-bill-form";
import type { Bill } from "@stark/api";
import { Dialog, DialogContent } from "@stark/ui/components/dialog";

export function RenameBillDialog({
  bill,
  open,
  onClose,
}: {
  bill: Bill;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => next || onClose()}>
      <DialogContent>
        <RenameBillForm bill={bill} onDone={onClose} />
      </DialogContent>
    </Dialog>
  );
}
