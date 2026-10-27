import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { Link } from "@tanstack/react-router";

export function PayBillButton() {
  return (
    <Button
      size="sm"
      nativeButton={false}
      render={<Link to="/pay" aria-label="Pay a bill" />}
      className="size-9.5 px-0 sm:size-auto sm:px-4"
    >
      <Icons.Add size={14} />
      <span className="hidden sm:inline">Pay a bill</span>
    </Button>
  );
}
