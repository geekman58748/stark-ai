import type { Bill } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@stark/ui/components/dropdown-menu";
import { Icons } from "@stark/ui/components/icons";

export type BillEdit = "rename" | "plan" | "remove";

export function BillEditMenu({ bill, onEdit }: { bill: Bill; onEdit: (edit: BillEdit) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="secondary" />}>
        Edit
        <Icons.ChevronDown size={14} />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-44">
        <DropdownMenuItem onClick={() => onEdit("rename")}>Rename</DropdownMenuItem>
        {bill.plan ? (
          <DropdownMenuItem onClick={() => onEdit("plan")}>Change plan</DropdownMenuItem>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={() => onEdit("remove")}>
          Remove bill
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
