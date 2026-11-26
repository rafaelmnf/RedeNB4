import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Pulseira, type PulseiraAtualizar, type PulseiraCriar } from "./cliente";
import { invalidarCadastros } from "./invalidar";

const CHAVE = ["pulseiras"] as const;

export function usePulseiras() {
  return useQuery({
    queryKey: CHAVE,
    // Sem polling: o status ao vivo vem do WebSocket (aoVivo) e as mudanças de
    // cadastro chegam como mensagem 'cadastro', que invalida esta consulta.
    queryFn: () => api<Pulseira[]>("/api/pulseiras"),
  });
}

export function useCadastrarPulseira() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: PulseiraCriar) => api<Pulseira>("/api/pulseiras", { method: "POST", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useAtualizarPulseira() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...dados }: PulseiraAtualizar & { id: number }) =>
      api<Pulseira>(`/api/pulseiras/${id}`, { method: "PATCH", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

export function useRemoverPulseira() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api<{ resultado: "arquivada" | "excluida" }>(`/api/pulseiras/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidarCadastros(qc),
  });
}
