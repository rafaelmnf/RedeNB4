import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo, useSyncExternalStore } from "react";

import type { Alerta, Cartao } from "../api/cliente";
import { aoVivo } from "./armazenar";
import { iniciarConexao } from "./conexao";

/** Mantém uma única conexão /ws/ao-vivo para o app inteiro. */
export function AoVivoProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  useEffect(() => iniciarConexao(qc), [qc]);
  return <>{children}</>;
}

/** Cartões de todas as pulseiras ativas (na ordem do servidor: vinculadas primeiro). */
export function useCartoes(): Cartao[] {
  return useSyncExternalStore(aoVivo.assinar, aoVivo.obterLista);
}

export function useCartoesPorId(): Map<number, Cartao> {
  const lista = useCartoes();
  return useMemo(() => new Map(lista.map((c) => [c.pulseira_id, c])), [lista]);
}

export function useCartao(id: number): Cartao | undefined {
  return useSyncExternalStore(aoVivo.assinar, () => aoVivo.obterCartao(id));
}

/** Alertas abertos (reconhecidos ou não). */
export function useAlertasAbertos(): Alerta[] {
  return useSyncExternalStore(aoVivo.assinar, aoVivo.obterAlertas);
}

export function useConexao() {
  return useSyncExternalStore(aoVivo.assinar, aoVivo.obterConexao);
}

// ---- relógio compartilhado: um único setInterval para todos os "há X s"
let agora = Date.now();
const ouvintesRelogio = new Set<() => void>();
let relogio: ReturnType<typeof setInterval> | undefined;

function assinarRelogio(cb: () => void) {
  ouvintesRelogio.add(cb);
  relogio ??= setInterval(() => {
    agora = Date.now();
    for (const ouvinte of ouvintesRelogio) ouvinte();
  }, 1000);
  return () => {
    ouvintesRelogio.delete(cb);
    if (ouvintesRelogio.size === 0) {
      clearInterval(relogio);
      relogio = undefined;
    }
  };
}

/** Re-renderiza o componente a cada segundo (para os textos "há X s"). */
export function useAgora(): number {
  return useSyncExternalStore(assinarRelogio, () => agora);
}
