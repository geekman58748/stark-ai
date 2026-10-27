import { Button } from "@stark/ui/components/button";
import { Link } from "@tanstack/react-router";

export function WalletActions() {
  return (
    <div className="flex flex-wrap gap-2">
      <Button nativeButton={false} render={<Link to="/wallet/add" />}>
        Add test money
      </Button>
    </div>
  );
}
