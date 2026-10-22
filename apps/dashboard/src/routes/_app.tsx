import { stateQuery } from "@stark/api";
import { createFileRoute, Outlet } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { QueryError } from "@/components/query-error";

export const Route = createFileRoute("/_app")({
  loader: ({ context }) => context.queryClient.query({ ...stateQuery(), staleTime: "static" }),
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
  errorComponent: (props) => (
    <AppShell>
      <QueryError {...props} />
    </AppShell>
  ),
});
