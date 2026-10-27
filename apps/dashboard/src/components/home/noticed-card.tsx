import { NoticedItem } from "@/components/home/noticed-item";
import type { Suggestion } from "@stark/api";
import { Card } from "@stark/ui/components/card";
import { Eyebrow } from "@stark/ui/components/eyebrow";

export function NoticedCard({ suggestions }: { suggestions: Suggestion[] }) {
  return (
    <Card className="gap-2.5">
      <Eyebrow>Stark noticed</Eyebrow>
      {suggestions.map((sug) => (
        <NoticedItem key={sug.id} suggestion={sug} />
      ))}
    </Card>
  );
}
