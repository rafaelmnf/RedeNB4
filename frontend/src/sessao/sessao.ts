import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ErroApi, type Usuario } from "../api/cliente";

export const CHAVE_SESSAO = ["sessao"] as const;

/** Usuário logado, ou null se não houver sessão (a API respondeu 401). */
export function useSessao() {
  return useQuery({
    queryKey: CHAVE_SESSAO,
    queryFn: async () => {
      try {
        return await api<Usuario>("/api/auth/eu");
      } catch (e) {
        if (e instanceof ErroApi && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: Infinity,
    retry: false,
  });
}

export function useUsuario(): Usuario | null {
  return useSessao().data ?? null;
}

/** Só o admin cadastra, edita, remove e vincula. O leitor vê tudo e reconhece alertas. */
export function usePodeEditar(): boolean {
  return useUsuario()?.papel === "admin";
}

export function useEntrar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dados: { email: string; senha: string }) =>
      api<Usuario>("/api/auth/login", { method: "POST", json: dados }),
    onSuccess: (u) => {
      qc.clear(); // nada do usuário anterior fica em cache
      qc.setQueryData(CHAVE_SESSAO, u);
    },
  });
}

export function useSair() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<null>("/api/auth/logout", { method: "POST" }),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(CHAVE_SESSAO, null);
    },
  });
}

export function useTrocarSenha() {
  return useMutation({
    mutationFn: (dados: { senha_atual: string; nova_senha: string }) =>
      api<null>("/api/auth/senha", { method: "POST", json: dados }),
  });
}
