import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";

export function FundMethodCard({
  name,
  detail,
}: {
  name: string;
  detail: string;
}) {
  return (
    <Card className="gap-2.5">
      <Eyebrow>{name}</Eyebrow>
      <span className="text-[15px]">{detail}</span>
      <span className="text-xs text-muted-foreground">
        Demo mode: the money shows up in your balance straight away.
      </span>
    </Card>
  );
}
