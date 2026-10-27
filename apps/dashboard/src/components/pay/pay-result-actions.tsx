import { Button } from "@stark/ui/components/button";
import { Link } from "@tanstack/react-router";

export function PayResultActions({ onAgain }: { onAgain: () => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button nativeButton={false} render={<Link to="/" />}>
        Done
      </Button>
      <Button variant="secondary" onClick={onAgain}>
        Pay another bill
      </Button>
    </div>
  );
}
