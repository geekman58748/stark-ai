import { stateQuery } from "@stark/api";
import { createFileRoute, Outlet } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { QueryError } from "@/components/query-error";

// Every signed-in screen shares the header, dock and phone tab bar.
export const Route = createFileRoute("/_app")({
  loader: ({ context }) => context.queryClient.ensureQueryData(stateQuery()),
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
