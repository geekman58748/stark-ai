import { useRouterState } from "@tanstack/react-router";

export function usePath() {
  return useRouterState({ select: (s) => s.location.pathname });
}
