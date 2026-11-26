import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type RegistroAuditoria, type Usuario, type UsuarioAtualizar, type UsuarioCriar } from "./cliente";

const CHAVE = ["usuarios"] as const;

export function useUsuarios() {
  return useQuery({ queryKey: CHAVE, queryFn: () => api<Usuario[]>("/api/usuarios") });
}

function useMutacao<T>(fn: (dados: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CHAVE });
      qc.invalidateQueries({ queryKey: ["auditoria"] });
    },
  });
}

export const useCriarUsuario = () =>
  useMutacao((dados: UsuarioCriar) => api<Usuario>("/api/usuarios", { method: "POST", json: dados }));

export const useAtualizarUsuario = () =>
  useMutacao(({ id, ...dados }: UsuarioAtualizar & { id: number }) =>
    api<Usuario>(`/api/usuarios/${id}`, { method: "PATCH", json: dados }),
  );

export const useRedefinirSenha = () =>
  useMutacao(({ id, senha }: { id: number; senha: string }) =>
    api<null>(`/api/usuarios/${id}/senha`, { method: "POST", json: { senha } }),
  );

export const useEncerrarSessoes = () =>
  useMutacao((id: number) => api<null>(`/api/usuarios/${id}/encerrar-sessoes`, { method: "POST" }));

type FiltrosAuditoria = { usuario_id?: number; acao?: string; de?: string };

export function useAuditoria(filtros: FiltrosAuditoria) {
  const params = new URLSearchParams(
    Object.entries(filtros)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  );
  return useQuery({
    queryKey: ["auditoria", filtros],
    queryFn: () => api<RegistroAuditoria[]>(`/api/auditoria?${params}`),
  });
}

export function useAcoesAuditoria() {
  return useQuery({ queryKey: ["auditoria", "acoes"], queryFn: () => api<string[]>("/api/auditoria/acoes") });
}
