import type { ActivityFilter } from "@/lib/receipts/receipts";
import { PillTabs } from "@stark/ui/components/pill-tabs";

const filters: { value: ActivityFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "bills", label: "Bills paid" },
  { value: "in", label: "Money in" },
  { value: "declined", label: "Declined" },
];

export function ActivityFilters({
  value,
  onChange,
}: {
  value: ActivityFilter;
  onChange: (value: ActivityFilter) => void;
}) {
  return (
    <PillTabs label="Show" value={value} tabs={filters} onChange={onChange} />
  );
}
