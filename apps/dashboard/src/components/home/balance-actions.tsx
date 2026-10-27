import { Button } from "@stark/ui/components/button";
import { Link } from "@tanstack/react-router";

export function BalanceActions() {
  return (
    <div className="flex flex-wrap gap-2">
      <Button nativeButton={false} render={<Link to="/wallet/add" />}>
        Add test money
      </Button>
      <Button
        variant="secondary"
        nativeButton={false}
        render={<Link to="/wallet" />}
      >
        Wallet
      </Button>
    </div>
  );
}
