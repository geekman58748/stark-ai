import { StatusPill } from "@stark/ui/components/status-pill";
import { greeting } from "@stark/utils/format";

export function HomeHeader({
  firstName,
  needing,
}: {
  firstName: string;
  needing: number;
}) {
  const headline =
    needing === 0
      ? "Everything’s covered"
      : needing === 1
        ? "One thing needs you"
        : "Two things need you";

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] text-muted-foreground">
        {greeting()}, {firstName}
      </span>
      <div className="flex flex-wrap items-center gap-2.5">
        <h1 className="m-0 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em]">
          {headline}
        </h1>
        <StatusPill>Stark is on</StatusPill>
      </div>
    </div>
  );
}
