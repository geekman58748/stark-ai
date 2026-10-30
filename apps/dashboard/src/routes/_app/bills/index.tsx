import { stateQuery } from "@stark/api";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { AddAnotherBillButton } from "@/components/bills/add-another-bill-button";
import { BillGroup } from "@/components/bills/bill-group";
import { BillSectionTabs } from "@/components/bills/bill-section-tabs";
import { BillsEmpty } from "@/components/bills/bills-empty";
import { BillsHeader } from "@/components/bills/bills-header";
import { BillSections } from "@/lib/bills/bill-sections";
import { Bills } from "@/lib/bills/bills";

export const Route = createFileRoute("/_app/bills/")({
  validateSearch: z.object({
    section: z.enum(["all", "electricity", "phone", "home"]).optional(),
  }),
  head: () => ({ meta: [{ title: "Bills · Stark" }] }),
  component: BillsPage,
});

function BillsPage() {
  const { data: state } = useSuspenseQuery(stateQuery());
  const section = Route.useSearch().section ?? "all";
  const navigate = Route.useNavigate();

  const bills = BillSections.filter(state.bills, section);
  const attention = bills.filter((b) => Bills.status(b, state).attention);
  const fine = bills.filter((b) => !Bills.status(b, state).attention);

  return (
    <>
      <BillsHeader />
      <BillSectionTabs
        value={section}
        onChange={(value) =>
          navigate({
            search: { section: value === "all" ? undefined : value },
          })
        }
      />

      {attention.length ? (
        <BillGroup title="Needs attention" bills={attention} state={state} />
      ) : null}

      <BillGroup title="All good" bills={fine} state={state} />

      {bills.length ? <AddAnotherBillButton /> : <BillsEmpty />}
    </>
  );
}
