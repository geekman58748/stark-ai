import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { Link } from "@tanstack/react-router";

export function AddAnotherBillButton() {
  return (
    <Button
      variant="outline"
      size="lg"
      block
      nativeButton={false}
      render={<Link to="/bills/new" />}
      className="rounded-row border-dashed border-white/12 text-[13px] font-normal text-fg-2 dark:border-white/12 dark:bg-transparent"
    >
      <Icons.Add size={16} />
      Add internet, water or another meter
    </Button>
  );
}
