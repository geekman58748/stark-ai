import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";

export function TestMoneyNote() {
  return (
    <Card className="gap-2.5">
      <Eyebrow>Test money</Eyebrow>
      <span className="text-[15px]">
        There is no way to pay in real money yet, so nothing is charged.
      </span>
      <span className="text-xs text-muted-foreground">
        It shows up in your balance straight away and is marked as test money in your activity.
      </span>
    </Card>
  );
}
