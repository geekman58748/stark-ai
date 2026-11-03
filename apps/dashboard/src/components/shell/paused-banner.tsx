import { useSetPaused } from "@stark/api/mutations";
import { stateQuery } from "@stark/api/queries";
import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { Notice } from "@stark/ui/components/notice";
import { useSuspenseQuery } from "@tanstack/react-query";

export function PausedBanner() {
  const { data: state } = useSuspenseQuery(stateQuery());
  const setPaused = useSetPaused();

  if (!state.paused) return null;

  const handleResume = () => setPaused.mutate(false);

  return (
    <Notice
      icon={<Icons.Pause size={18} />}
      title="Stark is paused"
      actions={
        <Button onClick={handleResume} disabled={setPaused.isPending} className="min-h-10">
          Resume
        </Button>
      }
    >
      Nothing will be paid from any chat or the app until you resume.
    </Notice>
  );
}
