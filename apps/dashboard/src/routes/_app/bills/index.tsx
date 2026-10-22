import { stateQuery } from "@stark/api";
import { buttonVariants } from "@stark/ui/button";
import { cn } from "@stark/ui/cn";
import { Icons } from "@stark/ui/icons";
import { RowList } from "@stark/ui/list-row";
import { PillTabs } from "@stark/ui/pill-tabs";
import { SectionHeading } from "@stark/ui/section-heading";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { PageTitle } from "@/components/app-shell";
import { BillRow } from "@/components/bill-row";
import { billStatus } from "@/lib/bills";

const sections = {
  all: { label: "All", kinds: null },
  electricity: { label: "Electricity", kinds: ["electricity"] },
  phone: { label: "Airtime and data", kinds: ["airtime", "data"] },
  home: { label: "TV and internet", kinds: ["tv", "internet", "water"] },
} as const;

type Section = keyof typeof sections;

export const Route = createFileRoute("/_app/bills/")({
  validateSearch: z.object({
    section: z.enum(["all", "electricity", "phone", "home"]).optional(),
  }),
  head: () => ({ meta: [{ title: "Bills · Stark" }] }),
  component: Bills,
});

function Bills() {
  const { data: state } = useSuspenseQuery(stateQuery());
  const section = Route.useSearch().section ?? "all";
  const navigate = Route.useNavigate();

  const kinds = sections[section].kinds as readonly string[] | null;
  const bills = state.bills.filter((b) => !kinds || kinds.includes(b.kind));
  const attention = bills.filter((b) => billStatus(b, state).attention);
  const fine = bills.filter((b) => !billStatus(b, state).attention);

  return (
    <>
      <PageTitle
        aside={
          <Link to="/bills/new" className={cn(buttonVariants(), "hover:text-white")}>
            <Icons.Add size={14} />
            Add a bill
          </Link>
        }
      >
        Bills
      </PageTitle>
      <p className="m-0 -mt-2 text-fg-2">
        Stark watches these and tells you before anything runs out.
      </p>
      <PillTabs<Section>
        label="Bill types"
        value={section}
        onChange={(value) => navigate({ search: { section: value === "all" ? undefined : value } })}
        tabs={Object.entries(sections).map(([value, s]) => ({
          value: value as Section,
          label: s.label,
        }))}
      />

      {attention.length ? (
        <>
          <SectionHeading action={attention.length}>Needs attention</SectionHeading>
          <RowList>
            {attention.map((b) => (
              <BillRow key={b.id} bill={b} state={state} />
            ))}
          </RowList>
        </>
      ) : null}

      <SectionHeading action={fine.length}>All good</SectionHeading>
      <RowList>
        {fine.map((b) => (
          <BillRow key={b.id} bill={b} state={state} />
        ))}
        {!bills.length ? <p className="m-0 text-[13px] text-muted">No bills here yet.</p> : null}
      </RowList>

      <Link
        to="/bills/new"
        className="flex items-center justify-center gap-2 rounded-row border border-dashed border-white/12 p-4 text-[13px] text-fg-2 no-underline hover:text-fg"
      >
        <Icons.Add size={16} />
        Add internet, water or another meter
      </Link>
    </>
  );
}
