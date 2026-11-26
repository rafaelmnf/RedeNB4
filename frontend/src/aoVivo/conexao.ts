import type { QueryClient } from "@tanstack/react-query";

import { type Alerta, api, type Cartao, SESSAO_EXPIRADA } from "../api/cliente";
import { invalidarCadastros } from "../api/invalidar";
import { aoVivo } from "./armazenar";

type Mensagem =
  | { tipo: "snapshot"; pulseiras: Cartao[]; alertas: Alerta[] }
  | { tipo: "alerta"; evento: "inicio" | "atualizacao" | "fim" | "reconhecido"; alerta: Alerta }
  | { tipo: "leitura"; cartao: Cartao; ts: string; bpm: number }
  | { tipo: "status"; cartao: Cartao }
  | { tipo: "cadastro" };

const ATRASO_MAX_MS = 10_000;
/** Código de fechamento do servidor quando não há login (ou a sessão foi encerrada). */
const SEM_SESSAO = 4401;

function urlWebSocket(): string {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  return `${protocolo}://${location.host}/ws/ao-vivo`;
}

/** Abre o WebSocket /ws/ao-vivo e o mantém: reconecta com espera crescente
 * (1 s, 2 s, 4 s… até 10 s). Devolve a função que encerra a conexão. */
export function iniciarConexao(qc: QueryClient): () => void {
  let ws: WebSocket | undefined;
  let tentativas = 0;
  let encerrado = false;
  let temporizador: ReturnType<typeof setTimeout> | undefined;

  async function preencherGraficos() {
    try {
      aoVivo.preencher(await api<Record<string, [number, number][]>>("/api/leituras/recentes?minutos=60"));
    } catch {
      // sem histórico recente: os gráficos começam vazios e enchem com as leituras ao vivo
    }
  }

  function tratar(msg: Mensagem) {
    switch (msg.tipo) {
      case "snapshot":
        aoVivo.aplicarSnapshot(msg.pulseiras, msg.alertas ?? []);
        break;
      case "leitura":
        aoVivo.atualizarCartao(msg.cartao);
        aoVivo.adicionarPonto(msg.cartao.pulseira_id, Date.parse(msg.ts) / 1000, msg.bpm);
        break;
      case "status":
        aoVivo.atualizarCartao(msg.cartao);
        break;
      case "alerta":
        aoVivo.atualizarAlerta(msg.alerta);
        if (msg.evento !== "atualizacao") qc.invalidateQueries({ queryKey: ["alertas"] });
        break;
      case "cadastro":
        // pulseira cadastrada/desativada ou vínculo mudou: pede o estado completo de novo
        ws?.send(JSON.stringify({ tipo: "snapshot" }));
        invalidarCadastros(qc);
        break;
    }
  }

  function conectar() {
    aoVivo.definirConexao(tentativas === 0 ? "conectando" : "reconectando");
    const socket = new WebSocket(urlWebSocket());
    ws = socket;
    socket.onopen = () => {
      tentativas = 0;
      aoVivo.definirConexao("ao_vivo");
      void preencherGraficos();
      invalidarCadastros(qc); // o que mudou enquanto estava desconectado
    };
    socket.onmessage = (ev) => {
      try {
        tratar(JSON.parse(ev.data) as Mensagem);
      } catch (e) {
        console.error("Mensagem ao vivo inválida", e);
      }
    };
    socket.onclose = (ev) => {
      if (encerrado || ws !== socket) return;
      if (ev.code === SEM_SESSAO) {
        encerrado = true; // não adianta reconectar: precisa entrar de novo
        window.dispatchEvent(new Event(SESSAO_EXPIRADA));
        return;
      }
      aoVivo.definirConexao("reconectando");
      const atraso = Math.min(ATRASO_MAX_MS, 1000 * 2 ** tentativas);
      tentativas++;
      temporizador = setTimeout(conectar, atraso);
    };
    socket.onerror = () => socket.close();
  }

  conectar();
  return () => {
    encerrado = true;
    clearTimeout(temporizador);
    ws?.close();
  };
}
