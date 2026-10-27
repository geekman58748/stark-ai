import { Eyebrow } from "@stark/ui/components/eyebrow";

export function MeterHeadline({ daysLeft }: { daysLeft: number }) {
  return (
    <>
      <Eyebrow>Light left</Eyebrow>
      <div className="flex flex-wrap items-baseline gap-2.5">
        <span className="font-serif text-5xl leading-none">
          About {daysLeft} days
        </span>
        <span className="text-xs text-muted-foreground">
          estimated from your top-ups
        </span>
      </div>
    </>
  );
}
