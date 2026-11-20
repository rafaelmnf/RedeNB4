import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  type Experimento,
  type ExperimentoAtualizar,
  type ExperimentoCriar,
  type SituacaoExperimento,
} from "./cliente";
import { invalidarCadastros } from "./invalidar";

type Filtros = { laboratorio_id?: number; situacao?: SituacaoExperimento };

export function useExperimentos(filtros: Filtros = {}) {
  const params = new URLSearchParams(
    Object.entries(filtros)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  );
  return useQuery({
    queryKey: ["experimentos", filtros],
    queryFn: () => api<Experimento[]>(`/api/experimentos?${params}`),
  });
}

export function useCriarExperimento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: ExperimentoCriar) => api<Experimento>("/api/experimentos", { method: "POST", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useAtualizarExperimento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...dados }: ExperimentoAtualizar & { id: number }) =>
      api<Experimento>(`/api/experimentos/${id}`, { method: "PATCH", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

/** Grava fim = agora. */
export function useEncerrarExperimento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<Experimento>(`/api/experimentos/${id}/encerrar`, { method: "POST" }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useRemoverExperimento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/experimentos/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidarCadastros(qc),
  });
}
