import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Pesquisador, type PesquisadorAtualizar, type PesquisadorCriar } from "./cliente";
import { invalidarCadastros } from "./invalidar";

export function usePesquisadores() {
  return useQuery({
    queryKey: ["pesquisadores"],
    queryFn: () => api<Pesquisador[]>("/api/pesquisadores"),
  });
}

export function useCadastrarPesquisador() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: PesquisadorCriar) =>
      api<Pesquisador>("/api/pesquisadores", { method: "POST", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useAtualizarPesquisador() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...dados }: PesquisadorAtualizar & { id: number }) =>
      api<Pesquisador>(`/api/pesquisadores/${id}`, { method: "PATCH", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useRemoverPesquisador() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/pesquisadores/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidarCadastros(qc),
  });
}
