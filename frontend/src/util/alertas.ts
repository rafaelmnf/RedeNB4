import type { Alerta, TipoAlerta } from "../api/cliente";

export const TIPOS_ALERTA: Record<TipoAlerta, { rotulo: string; cor: string }> = {
  bpm_alto: { rotulo: "BPM alto", cor: "red" },
  bpm_baixo: { rotulo: "BPM baixo", cor: "grape" },
  sem_sinal: { rotulo: "Sem sinal", cor: "orange" },
  fora_do_braco: { rotulo: "Fora do braço", cor: "yellow" },
};

/** Ex.: "BPM 172 acima de 150", "Sem sinal", "Fora do braço". */
export function descreverAlerta(a: Alerta): string {
  switch (a.tipo) {
    case "bpm_alto":
      return `BPM ${a.valor} acima de ${a.limite}`;
    case "bpm_baixo":
      return `BPM ${a.valor} abaixo de ${a.limite}`;
    case "sem_sinal":
      return "Sem sinal";
    case "fora_do_braco":
      return "Fora do braço";
  }
}

/** Duração legível: "45 s", "3 min", "1 h 05 min". */
export function duracao(desdeIso: string, ateIso?: string | null): string {
  const s = Math.max(0, Math.round(((ateIso ? Date.parse(ateIso) : Date.now()) - Date.parse(desdeIso)) / 1000));
  if (s < 60) return `${s} s`;
  const min = Math.floor(s / 60);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min`;
}
