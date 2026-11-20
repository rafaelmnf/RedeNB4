import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Laboratorio, type LaboratorioAtualizar, type LaboratorioCriar } from "./cliente";
import { invalidarCadastros } from "./invalidar";

export function useLaboratorios() {
  return useQuery({
    queryKey: ["laboratorios"],
    queryFn: () => api<Laboratorio[]>("/api/laboratorios"),
  });
}

export function useCadastrarLaboratorio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: LaboratorioCriar) => api<Laboratorio>("/api/laboratorios", { method: "POST", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useAtualizarLaboratorio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...dados }: LaboratorioAtualizar & { id: number }) =>
      api<Laboratorio>(`/api/laboratorios/${id}`, { method: "PATCH", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useRemoverLaboratorio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/laboratorios/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidarCadastros(qc),
  });
}
