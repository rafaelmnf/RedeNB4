/** Buffer circular de pontos (tempo em segundos epoch, valor) com capacidade fixa.
 * Mantém só os mais recentes e ignora pontos fora de ordem (ex.: repetidos ao
 * reconectar e preencher pelo banco). */
export class BufferCircular {
  private readonly t: Float64Array;
  private readonly v: Float64Array;
  private inicio = 0;
  private tamanho = 0;

  constructor(readonly capacidade: number) {
    this.t = new Float64Array(capacidade);
    this.v = new Float64Array(capacidade);
  }

  get length(): number {
    return this.tamanho;
  }

  ultimoTempo(): number | undefined {
    if (this.tamanho === 0) return undefined;
    return this.t[(this.inicio + this.tamanho - 1) % this.capacidade];
  }

  adicionar(tempo: number, valor: number): boolean {
    const ultimo = this.ultimoTempo();
    if (ultimo !== undefined && tempo <= ultimo) return false;
    const i = (this.inicio + this.tamanho) % this.capacidade;
    this.t[i] = tempo;
    this.v[i] = valor;
    if (this.tamanho < this.capacidade) this.tamanho++;
    else this.inicio = (this.inicio + 1) % this.capacidade;
    return true;
  }

  /** Pontos com tempo >= `desde`, em ordem: [tempos, valores]. */
  janela(desde = -Infinity): [number[], number[]] {
    const ts: number[] = [];
    const vs: number[] = [];
    for (let k = 0; k < this.tamanho; k++) {
      const i = (this.inicio + k) % this.capacidade;
      if (this.t[i] >= desde) {
        ts.push(this.t[i]);
        vs.push(this.v[i]);
      }
    }
    return [ts, vs];
  }
}
