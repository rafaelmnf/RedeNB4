import { Alert, Center, Loader } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { SESSAO_EXPIRADA } from "../api/cliente";
import { CHAVE_SESSAO, useSessao } from "./sessao";

/** Sem login, manda para /login (e volta para cá depois). Quando a API ou o WebSocket
 * avisam que a sessão caiu (evento SESSAO_EXPIRADA), faz o mesmo. */
export function RotaProtegida({ children }: { children: ReactNode }) {
  const { data: usuario, isLoading, error } = useSessao();
  const qc = useQueryClient();
  const { pathname, search } = useLocation();

  useEffect(() => {
    const cair = () => qc.setQueryData(CHAVE_SESSAO, null);
    window.addEventListener(SESSAO_EXPIRADA, cair);
    return () => window.removeEventListener(SESSAO_EXPIRADA, cair);
  }, [qc]);

  if (isLoading)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    );
  if (error) return <Alert color="red">Servidor indisponível: {error.message}</Alert>;
  if (!usuario) return <Navigate to={`/login?volta=${encodeURIComponent(pathname + search)}`} replace />;
  return <>{children}</>;
}

/** Página só para admin (Usuários, Auditoria). */
export function SoAdmin({ children }: { children: ReactNode }) {
  const { data: usuario } = useSessao();
  if (usuario?.papel !== "admin") {
    return (
      <Alert color="yellow" title="Sem permissão">
        Esta página é só para administradores.
      </Alert>
    );
  }
  return <>{children}</>;
}
