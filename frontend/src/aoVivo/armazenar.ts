import type { Alerta, Cartao } from "../api/cliente";
import { BufferCircular } from "../util/BufferCircular";

export type EstadoConexao = "conectando" | "ao_vivo" | "reconectando";

/** ~60 min a 1 ponto a cada 2 s (intervalo do AP). */
const CAPACIDADE_BUFFER = 2000;

type Ouvinte = () => void;

/** Estado ao vivo do app inteiro, fora do React (lido com useSyncExternalStore).
 *
 * - cartões: um por pulseira ativa, trocados a cada mensagem do WebSocket;
 * - buffers: pontos de BPM por pulseira para os gráficos. Os gráficos assinam os
 *   pontos novos à parte, para não re-renderizar o React a cada leitura. */
class ArmazenamentoAoVivo {
  private cartoes = new Map<number, Cartao>();
  private lista: Cartao[] = [];
  private alertas = new Map<number, Alerta>();        // abertos, por id
  private listaAlertas: Alerta[] = [];
  private estadoConexao: EstadoConexao = "conectando";
  private buffers = new Map<number, BufferCircular>();
  private ouvintes = new Set<Ouvinte>();
  private ouvintesPontos = new Map<number, Set<Ouvinte>>();

  // ---- leitura (estável entre chamadas, como pede o useSyncExternalStore)
  obterLista = (): Cartao[] => this.lista;
  obterConexao = (): EstadoConexao => this.estadoConexao;
  obterCartao = (id: number): Cartao | undefined => this.cartoes.get(id);
  /** Alertas abertos (reconhecidos ou não), mais antigos primeiro. */
  obterAlertas = (): Alerta[] => this.listaAlertas;

  buffer(id: number): BufferCircular {
    let b = this.buffers.get(id);
    if (!b) this.buffers.set(id, (b = new BufferCircular(CAPACIDADE_BUFFER)));
    return b;
  }

  // ---- assinaturas
  assinar = (cb: Ouvinte): (() => void) => {
    this.ouvintes.add(cb);
    return () => this.ouvintes.delete(cb);
  };

  assinarPontos(id: number, cb: Ouvinte): () => void {
    let s = this.ouvintesPontos.get(id);
    if (!s) this.ouvintesPontos.set(id, (s = new Set()));
    s.add(cb);
    return () => s.delete(cb);
  }

  private notificar() {
    this.lista = [...this.cartoes.values()];
    for (const cb of this.ouvintes) cb();
  }

  private notificarPontos(id: number) {
    for (const cb of this.ouvintesPontos.get(id) ?? []) cb();
  }

  // ---- escrita (chamada pela conexão)
  definirConexao(estado: EstadoConexao) {
    if (estado === this.estadoConexao) return;
    this.estadoConexao = estado;
    for (const cb of this.ouvintes) cb();
  }

  private atualizarListaAlertas() {
    this.listaAlertas = [...this.alertas.values()].sort((a, b) => a.inicio.localeCompare(b.inicio));
  }

  /** Substitui todos os cartões (a ordem do servidor é mantida) e os alertas abertos. */
  aplicarSnapshot(cartoes: Cartao[], alertas: Alerta[]) {
    this.cartoes = new Map(cartoes.map((c) => [c.pulseira_id, c]));
    this.alertas = new Map(alertas.map((a) => [a.id, a]));
    this.atualizarListaAlertas();
    for (const id of [...this.buffers.keys()]) if (!this.cartoes.has(id)) this.buffers.delete(id);
    this.notificar();
  }

  atualizarCartao(c: Cartao) {
    if (!this.cartoes.has(c.pulseira_id)) return; // pulseira saiu; o snapshot seguinte resolve
    this.cartoes.set(c.pulseira_id, c);
    this.notificar();
  }

  /** Alerta começou, mudou (valor extremo, reconhecido) ou terminou (fim preenchido). */
  atualizarAlerta(a: Alerta) {
    if (a.fim) this.alertas.delete(a.id);
    else this.alertas.set(a.id, a);
    this.atualizarListaAlertas();
    for (const cb of this.ouvintes) cb();
  }

  adicionarPonto(id: number, tempoS: number, bpm: number) {
    if (this.buffer(id).adicionar(tempoS, bpm)) this.notificarPontos(id);
  }

  /** Preenche os buffers com os pontos do banco (ao abrir ou reconectar), mantendo
   * os pontos ao vivo que chegaram enquanto a consulta estava em andamento. */
  preencher(series: Record<string, [number, number][]>) {
    for (const [chave, pontos] of Object.entries(series)) {
      const id = Number(chave);
      const anterior = this.buffers.get(id);
      const novo = new BufferCircular(CAPACIDADE_BUFFER);
      for (const [t, v] of pontos) novo.adicionar(t, v);
      if (anterior) {
        const [ts, vs] = anterior.janela();
        ts.forEach((t, i) => novo.adicionar(t, vs[i]));
      }
      this.buffers.set(id, novo);
      this.notificarPontos(id);
    }
  }
}

export const aoVivo = new ArmazenamentoAoVivo();
