import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type Alerta, api, type Limites, type LimitesEntrada } from "./cliente";

export function useAlertas(filtros: { abertos?: boolean } = {}) {
  const params = filtros.abertos === undefined ? "" : `?abertos=${filtros.abertos}`;
  return useQuery({
    queryKey: ["alertas", filtros],
    queryFn: () => api<Alerta[]>(`/api/alertas${params}`),
  });
}

/** Marca o alerta como visto. O WebSocket atualiza o banner e os cards. */
export function useReconhecer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<Alerta>(`/api/alertas/${id}/reconhecer`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alertas"] }),
  });
}

export function useLimites() {
  return useQuery({ queryKey: ["limites"], queryFn: () => api<Limites>("/api/limites") });
}

export function useSalvarLimites() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: LimitesEntrada) => api<Limites>("/api/limites", { method: "PUT", json: dados }),
    onSuccess: (lim) => qc.setQueryData(["limites"], lim),
  });
}
