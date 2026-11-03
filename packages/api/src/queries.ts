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
  approvals: ["approvals"] as const,
  demo: ["demo"] as const,
  payees: ["payees"] as const,
  fundingMethods: ["wallet", "methods"] as const,
  cryptoAssets: ["wallet", "crypto-assets"] as const,
  deposit: (id: string) => ["wallet", "deposits", id] as const,
  banks: ["wallet", "banks"] as const,
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

/** A request expires in minutes, so poll it like State. */
export const approvalsQuery = () =>
  queryOptions({ queryKey: queryKeys.approvals, queryFn: api.approvals, refetchInterval: 30_000 });

export const demoQuery = () => queryOptions({ queryKey: queryKeys.demo, queryFn: api.demo });

export const payeesQuery = () => queryOptions({ queryKey: queryKeys.payees, queryFn: api.payees });

export const fundingMethodsQuery = () =>
  queryOptions({ queryKey: queryKeys.fundingMethods, queryFn: api.fundingMethods });

export const cryptoAssetsQuery = () =>
  queryOptions({
    queryKey: queryKeys.cryptoAssets,
    queryFn: api.cryptoAssets,
    staleTime: 10 * 60_000,
  });

/** A deposit settles off-screen (a bank page, another wallet), so poll it until it does. */
export const depositQuery = (id: string) =>
  queryOptions({
    queryKey: queryKeys.deposit(id),
    queryFn: () => api.deposit(id),
    refetchInterval: (query) => {
      // No status yet (the first read failed) keeps polling too, or a deposit started
      // while the API blinked would wait on "open" forever.
      const status = query.state.data?.status;
      return status === undefined || status === "open" || status === "confirming" ? 5_000 : false;
    },
  });

export const banksQuery = () =>
  queryOptions({ queryKey: queryKeys.banks, queryFn: api.banks, staleTime: 60 * 60_000 });
