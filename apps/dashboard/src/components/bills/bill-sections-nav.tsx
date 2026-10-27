import type { Bill } from "@stark/api";
import { pillTabClass } from "@stark/ui/components/pill-tabs";
import { Link } from "@tanstack/react-router";

export function BillSectionsNav({ bill }: { bill: Bill }) {
  return (
    <nav aria-label="Sections" className="flex flex-wrap gap-2">
      <span aria-current="page" className={pillTabClass(true)}>
        Overview
      </span>
      <Link
        to="/activity"
        search={{ bill: bill.id }}
        className={pillTabClass(false)}
      >
        History
      </Link>
      <Link to="/settings" className={pillTabClass(false)}>
        Limits
      </Link>
    </nav>
  );
}
