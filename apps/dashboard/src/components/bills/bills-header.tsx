import { PageTitle } from "@/components/shell/page-title";
import { Button } from "@stark/ui/components/button";
import { Icons } from "@stark/ui/components/icons";
import { Link } from "@tanstack/react-router";

export function BillsHeader() {
  return (
    <>
      <PageTitle
        aside={
          <Button nativeButton={false} render={<Link to="/bills/new" />}>
            <Icons.Add size={14} />
            Add a bill
          </Button>
        }
      >
        Bills
      </PageTitle>
      <p className="m-0 -mt-2 text-fg-2">
        Stark watches these and tells you before anything runs out.
      </p>
    </>
  );
}
