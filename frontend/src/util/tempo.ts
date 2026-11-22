import dayjs from "dayjs";
import "dayjs/locale/pt-br";
import relativeTime from "dayjs/plugin/relativeTime";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);
dayjs.locale("pt-br");

/** Os horários vêm do backend em UTC; a exibição é sempre no fuso do laboratório. */
export const FUSO = "America/Sao_Paulo";

export function formatarDataHora(iso: string | null | undefined): string {
  return iso ? dayjs(iso).tz(FUSO).format("DD/MM/YYYY HH:mm:ss") : "—";
}

export function haQuantoTempo(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `há ${s} s`;
  return dayjs(iso).fromNow();
}

/** Datas sem hora (ex.: nascimento, 'YYYY-MM-DD'): sem conversão de fuso. */
export function formatarData(iso: string | null | undefined): string {
  return iso ? dayjs(iso).format("DD/MM/YYYY") : "—";
}

/** ISO (UTC) -> valor de <input type="datetime-local"> no fuso do navegador. */
export function paraInputLocal(iso: string | null | undefined): string {
  return iso ? dayjs(iso).format("YYYY-MM-DDTHH:mm") : "";
}

/** Valor de <input type="datetime-local"> -> ISO com fuso (null se vazio). */
export function deInputLocal(valor: string): string | null {
  return valor ? dayjs(valor).format() : null;
}

/** Segundos epoch (como no uPlot) -> texto no fuso do laboratório, ex.: "DD/MM HH:mm". */
export function formatarEpoch(t: number, formato: string): string {
  return dayjs.unix(t).tz(FUSO).format(formato);
}
