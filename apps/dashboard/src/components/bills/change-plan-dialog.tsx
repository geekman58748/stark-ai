import type { Bill } from "@stark/api";
import { Dialog, DialogContent } from "@stark/ui/components/dialog";
import { ChangePlanForm } from "@/components/bills/change-plan-form";

export function ChangePlanDialog({
  bill,
  plan,
  open,
  onClose,
}: {
  bill: Bill;
  plan: string;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => next || onClose()}>
      <DialogContent>
        <ChangePlanForm bill={bill} plan={plan} onDone={onClose} />
      </DialogContent>
    </Dialog>
  );
}
