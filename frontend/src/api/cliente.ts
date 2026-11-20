import type { components } from "./schema";

export type Pulseira = components["schemas"]["PulseiraSaida"];
export type PulseiraCriar = components["schemas"]["PulseiraCriar"];
export type PulseiraAtualizar = components["schemas"]["PulseiraAtualizar"];
export type StatusPulseira = components["schemas"]["StatusSaida"];
export type Pesquisador = components["schemas"]["PesquisadorSaida"];
export type PesquisadorCriar = components["schemas"]["PesquisadorCriar"];
export type PesquisadorAtualizar = components["schemas"]["PesquisadorAtualizar"];
export type Atribuicao = components["schemas"]["AtribuicaoSaida"];
export type AtribuicaoCriar = components["schemas"]["AtribuicaoCriar"];

export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

/** Extrai uma mensagem legível do corpo de erro do FastAPI. */
function mensagemDeErro(corpo: unknown, status: number): string {
  const detalhe = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length > 0) {
    return detalhe.map((d: { msg?: string }) => (d.msg ?? "").replace(/^Value error, /, "")).join("; ");
  }
  return `Erro ${status}`;
}

export async function api<T>(caminho: string, opcoes: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...resto } = opcoes;
  const resp = await fetch(caminho, {
    credentials: "same-origin",
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: json !== undefined ? JSON.stringify(json) : resto.body,
    ...resto,
  });
  const texto = await resp.text();
  const corpo = texto ? JSON.parse(texto) : null;
  if (!resp.ok) throw new ErroApi(resp.status, mensagemDeErro(corpo, resp.status));
  return corpo as T;
}
