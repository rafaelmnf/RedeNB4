// Mesmas regras do backend (redenb4/dominio/mac.py). O backend valida de novo.
const FORMATOS = [
  /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/,
  /^([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}$/,
  /^([0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}$/,
  /^[0-9A-Fa-f]{12}$/,
];

/** Devolve o MAC no formato AA:BB:CC:DD:EE:FF, ou null se for inválido. */
export function normalizarMac(texto: string): string | null {
  const bruto = texto.trim();
  if (!FORMATOS.some((f) => f.test(bruto))) return null;
  const hexa = bruto.replace(/[:\-.]/g, "").toUpperCase();
  return hexa.match(/.{2}/g)!.join(":");
}
