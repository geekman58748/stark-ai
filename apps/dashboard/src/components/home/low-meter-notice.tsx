import type { Bill } from "@stark/api";
import { IconTile } from "@stark/ui/components/icon-tile";
import { Icons } from "@stark/ui/components/icons";
import { Notice } from "@stark/ui/components/notice";
import { LowMeterActions } from "@/components/home/low-meter-actions";

export function LowMeterNotice({ meter, daysLeft }: { meter: Bill; daysLeft: number | null }) {
  return (
    <Notice
      icon={
        <IconTile>
          <Icons.Electricity size={16} />
        </IconTile>
      }
      title={`${meter.label} meter is running low`}
      actions={<LowMeterActions meter={meter} />}
    >
      About {daysLeft} days left at your usual use.
    </Notice>
  );
}
