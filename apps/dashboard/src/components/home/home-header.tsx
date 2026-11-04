import { StatusPill } from "@stark/ui/components/status-pill";
import { greeting } from "@stark/utils/format";
import { HomeHeadline } from "@/lib/home/home-headline";

export function HomeHeader({
  firstName,
  needing,
  paused,
}: {
  firstName: string;
  needing: number;
  paused: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] text-muted-foreground">
        {greeting()}, {firstName}
      </span>
      <div className="flex flex-wrap items-center gap-2.5">
        <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
          {HomeHeadline.text(needing)}
        </h1>
        <StatusPill tone={paused ? "muted" : "brand"}>
          {paused ? "Stark is paused" : "Stark is on"}
        </StatusPill>
      </div>
    </div>
  );
}
