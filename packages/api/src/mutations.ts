import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { queryKeys } from "./queries";
import type {
  BillPatch,
  LimitsPatch,
  NewBill,
  PaymentInput,
  TopUpInput,
  WithdrawInput,
} from "./types";

// Money moved or a bill changed: balance, caps, units and history can all shift together.
function invalidateMoney(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: queryKeys.state }),
    qc.invalidateQueries({ queryKey: queryKeys.bills }),
    qc.invalidateQueries({ queryKey: queryKeys.activity }),
    qc.invalidateQueries({ queryKey: queryKeys.wallet }),
    qc.invalidateQueries({ queryKey: queryKeys.limits }),
    qc.invalidateQueries({ queryKey: queryKeys.suggestions }),
  ]);
}

export function usePayBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PaymentInput) => api.pay(input),
    onSettled: () => invalidateMoney(qc),
  });
}

export function useAddBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: NewBill) => api.addBill(input),
    onSuccess: () => invalidateMoney(qc),
  });
}

export function useUpdateBill(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: BillPatch) => api.updateBill(id, patch),
    onSuccess: (bill) => {
      qc.setQueryData(queryKeys.bill(id), bill);
      return invalidateMoney(qc);
    },
  });
}

export function useDeleteBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteBill(id),
    onSuccess: () => invalidateMoney(qc),
  });
}

export function useUpdateLimits() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: LimitsPatch) => api.updateLimits(patch),
    onSuccess: (limits) => {
      qc.setQueryData(queryKeys.limits, limits);
      return invalidateMoney(qc);
    },
  });
}

export function useTopUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TopUpInput) => api.topUp(input),
    onSuccess: () => invalidateMoney(qc),
  });
}

export function useWithdraw() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: WithdrawInput) => api.withdraw(input),
    onSuccess: () => invalidateMoney(qc),
  });
}

export function useVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transcript: string) => api.voice(transcript),
    onSuccess: (reply) => {
      if (reply.receipt_id) return invalidateMoney(qc);
    },
  });
}

export function useResetDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.resetDemo(),
    onSuccess: () => qc.invalidateQueries(),
  });
}
