import { queryOptions } from "@tanstack/react-query";
import { api } from "./client";
import type { BillKind } from "./types";

export const queryKeys = {
  state: ["state"] as const,
  bills: ["bills"] as const,
  bill: (id: string) => ["bills", id] as const,
  plans: (kind?: string, provider?: string) => ["plans", kind ?? "all", provider ?? "all"] as const,
  activity: ["activity"] as const,
  limits: ["limits"] as const,
  wallet: ["wallet"] as const,
  suggestions: ["suggestions"] as const,
};

/** Everything Home needs. There is no websocket, so poll gently and refetch after payments. */
export const stateQuery = () =>
  queryOptions({ queryKey: queryKeys.state, queryFn: api.state, refetchInterval: 30_000 });

export const billsQuery = () => queryOptions({ queryKey: queryKeys.bills, queryFn: api.bills });

export const billQuery = (id: string) =>
  queryOptions({ queryKey: queryKeys.bill(id), queryFn: () => api.bill(id) });

export const plansQuery = (kind?: Extract<BillKind, "data" | "tv">, provider?: string) =>
  queryOptions({
    queryKey: queryKeys.plans(kind, provider),
    queryFn: () => api.plans({ kind, provider }),
    staleTime: 10 * 60_000,
  });

export const activityQuery = () =>
  queryOptions({ queryKey: queryKeys.activity, queryFn: api.activity });

export const limitsQuery = () => queryOptions({ queryKey: queryKeys.limits, queryFn: api.limits });

export const walletQuery = () => queryOptions({ queryKey: queryKeys.wallet, queryFn: api.wallet });

export const suggestionsQuery = () =>
  queryOptions({ queryKey: queryKeys.suggestions, queryFn: api.suggestions });
