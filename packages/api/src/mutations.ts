import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { queryKeys } from "./queries";
import type { BillPatch, LimitsPatch, NewBill, PaymentInput, TopUpInput } from "./types";

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

export function useVoice() {
  const qc = useQueryClient();
  return useMutation({
    // speak: false — text first, always. The Talk screen fetches the voice
    // from api.speak once the words are on screen, so synthesis never delays
    // the reply you are waiting to read.
    mutationFn: (transcript: string) => api.voice(transcript, { speak: false }),
    onSuccess: (reply) => {
      if (reply.receipt_id) return invalidateMoney(qc);
    },
  });
}

/** Same contract as useVoice, but the clip goes up and the server does the
 *  hearing — for browsers without the Web Speech API. */
export function useVoiceAudio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (audio: Blob) => api.voiceAudio(audio, { speak: false }),
    onSuccess: (reply) => {
      if (reply.receipt_id) return invalidateMoney(qc);
    },
  });
}

/**
 * Mint a link code on demand. Deliberately not a query: each call creates a
 * new code, and a cached one would be a code the user cannot see.
 */
export function useLinkCode() {
  return useMutation({
    mutationFn: () => api.linkCode(),
  });
}

export function useResetDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.resetDemo(),
    onSuccess: () => qc.invalidateQueries(),
  });
}
