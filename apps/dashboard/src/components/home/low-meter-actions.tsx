import type { Bill } from "@stark/api";
import { Button } from "@stark/ui/components/button";
import { formatNaira } from "@stark/utils/format";
import { Link } from "@tanstack/react-router";

export function LowMeterActions({ meter }: { meter: Bill }) {
  return (
    <>
      <Button
        nativeButton={false}
        render={
          <Link
            to="/pay"
            search={{
              bill: meter.id,
              amount: meter.last_amount_ngn ?? undefined,
            }}
          />
        }
      >
        Top up {meter.last_amount_ngn ? formatNaira(meter.last_amount_ngn) : ""}
      </Button>
      <Button
        variant="secondary"
        nativeButton={false}
        render={<Link to="/bills" />}
      >
        Later
      </Button>
    </>
  );
}
