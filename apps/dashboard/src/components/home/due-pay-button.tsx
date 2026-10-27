import type { DueBill } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { formatNaira } from "@stark/utils/format";
import { Link } from "@tanstack/react-router";

export function DuePayButton({ due }: { due: DueBill }) {
  return (
    <Button
      nativeButton={false}
      render={
        <Link
          to="/pay"
          search={{ bill: due.id, amount: due.price_ngn ?? undefined }}
        />
      }
    >
      Pay{due.price_ngn ? ` ${formatNaira(due.price_ngn)}` : " it"}
    </Button>
  );
}
