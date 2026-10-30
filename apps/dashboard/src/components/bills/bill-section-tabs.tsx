import { PillTabs } from "@stark/ui/components/pill-tabs";
import { type BillSection, BillSections } from "@/lib/bills/bill-sections";

export function BillSectionTabs({
  value,
  onChange,
}: {
  value: BillSection;
  onChange: (section: BillSection) => void;
}) {
  return (
    <PillTabs<BillSection>
      label="Bill types"
      value={value}
      onChange={onChange}
      tabs={BillSections.tabs()}
    />
  );
}
