import { Button } from "@stark/ui/components/button";
import { CollapsibleTrigger } from "@stark/ui/components/collapsible";
import { Link } from "@tanstack/react-router";

export function WalletActions() {
  return (
    <div className="flex flex-wrap gap-2">
      <Button nativeButton={false} render={<Link to="/wallet/add" />}>
        Add money
      </Button>
      <CollapsibleTrigger render={<Button variant="secondary" />}>
        Withdraw to bank
      </CollapsibleTrigger>
    </div>
  );
}
