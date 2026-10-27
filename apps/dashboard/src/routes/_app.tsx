import { stateQuery } from "@stark/api";
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { AppShell } from "@/components/shell/app-shell";
import { QueryError } from "@/components/query-error";
import { sessionStore } from "@/lib/auth/session-store";

export const Route = createFileRoute("/_app")({
  // Every screen under here reads one person's wallet, so a missing session goes
  // to the sign-in page before a loader runs and the state query 401s.
  beforeLoad: () => {
    if (!sessionStore.token()) throw redirect({ to: "/login" });
  },
  loader: ({ context }) =>
    context.queryClient.query({ ...stateQuery(), staleTime: "static" }),
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
