import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Atribuicao, type AtribuicaoCriar } from "./cliente";
import { invalidarCadastros } from "./invalidar";

type Filtros = { ativa?: boolean; pulseira_id?: number; pesquisador_id?: number };

export function useAtribuicoes(filtros: Filtros, habilitado = true) {
  const params = new URLSearchParams(
    Object.entries(filtros)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  );
  return useQuery({
    queryKey: ["atribuicoes", filtros],
    queryFn: () => api<Atribuicao[]>(`/api/atribuicoes?${params}`),
    enabled: habilitado,
  });
}

/** Vincula a pulseira à pessoa (início = agora). */
export function useVincular() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: AtribuicaoCriar) => api<Atribuicao>("/api/atribuicoes", { method: "POST", json: dados }),
    onSuccess: () => invalidarCadastros(qc),
  });
}

/** Encerra o vínculo (fim = agora): a pulseira volta a "não vinculada". */
export function useDesvincular() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (atribuicaoId: number) =>
      api<Atribuicao>(`/api/atribuicoes/${atribuicaoId}/encerrar`, { method: "POST" }),
    onSuccess: () => invalidarCadastros(qc),
  });
}
