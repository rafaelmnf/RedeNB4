import { useComputedColorScheme, useMantineTheme } from "@mantine/core";
import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

import { aoVivo } from "../aoVivo/armazenar";
import { formatarEpoch, FUSO } from "../util/tempo";

type Cores = { linha: string; faixa: string; eixo: string; grade: string };

function useCores(): Cores {
  const tema = useMantineTheme();
  const escuro = useComputedColorScheme("light") === "dark";
  return {
    linha: tema.colors.teal[escuro ? 4 : 7],
    faixa: escuro ? "rgba(56, 217, 169, 0.15)" : "rgba(12, 166, 120, 0.15)",
    eixo: escuro ? tema.colors.dark[1] : tema.colors.gray[7],
    grade: escuro ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.07)",
  };
}

const tzDate = (ts: number) => uPlot.tzDate(new Date(ts * 1000), FUSO);

/** Faixa do eixo Y: as leituras com folga, nunca menor que 30 BPM de amplitude. */
function faixaY(_u: uPlot, min: number | null, max: number | null): uPlot.Range.MinMax {
  if (min == null || max == null) return [50, 110];
  const meio = (min + max) / 2;
  const meia = Math.max((max - min) / 2 + 8, 15);
  return [Math.max(0, Math.floor(meio - meia)), Math.ceil(meio + meia)];
}

/** Rótulos do eixo de tempo no padrão brasileiro. O primeiro tick e cada virada de
 * dia levam a data (DD/MM); os demais, só a hora. */
const rotulosTempo: uPlot.Axis.DynamicValues = (_u, splits, _eixo, _espaco, passo) => {
  if (passo >= 86400) return splits.map((t) => formatarEpoch(t, "DD/MM"));
  const hora = passo < 60 ? "HH:mm:ss" : "HH:mm";
  let diaAnterior = "";
  return splits.map((t) => {
    const dia = formatarEpoch(t, "DD/MM");
    const comData = dia !== diaAnterior;
    diaAnterior = dia;
    return formatarEpoch(t, comData ? `DD/MM ${hora}` : hora);
  });
};

/** Valor do tempo na legenda do cursor (o padrão do uPlot é o americano). */
const serieTempo: uPlot.Series = { value: (_u, t) => (t == null ? "—" : formatarEpoch(t, "DD/MM/YYYY HH:mm:ss")) };

function eixos(c: Cores, compacto: boolean): uPlot.Axis[] {
  const base = { stroke: c.eixo, grid: { stroke: c.grade, width: 1 }, ticks: { show: false } };
  return compacto
    ? [{ ...base, show: false }, { ...base, size: 32, values: (_u, vals) => vals.map((v) => String(v)) }]
    : [
        { ...base, values: rotulosTempo, space: 70 },
        { ...base, size: 40, label: "BPM", labelSize: 14 },
      ];
}

/** Cria o uPlot no elemento e o mantém do tamanho do container. */
function useUplot(
  ref: React.RefObject<HTMLDivElement | null>,
  altura: number,
  criarOpcoes: (largura: number) => uPlot.Options,
  dadosIniciais: () => uPlot.AlignedData,
  deps: unknown[],
) {
  const plot = useRef<uPlot | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const u = new uPlot(criarOpcoes(el.clientWidth || 300), dadosIniciais(), el);
    plot.current = u;
    const observador = new ResizeObserver(() => u.setSize({ width: el.clientWidth, height: altura }));
    observador.observe(el);
    return () => {
      observador.disconnect();
      u.destroy();
      plot.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return plot;
}

/** Gráfico ao vivo de uma pulseira: lê o buffer circular e redesenha no máximo uma
 * vez por frame (requestAnimationFrame), sem passar pelo estado do React. */
export function GraficoBpmAoVivo({
  pulseiraId,
  janelaS,
  altura = 80,
  compacto = true,
}: {
  pulseiraId: number;
  janelaS: number;
  altura?: number;
  compacto?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cores = useCores();
  const janela = useRef(janelaS);
  janela.current = janelaS;

  const dados = (): uPlot.AlignedData => {
    const agora = Date.now() / 1000;
    return aoVivo.buffer(pulseiraId).janela(agora - janela.current);
  };

  const plot = useUplot(
    ref,
    altura,
    (largura) => ({
      width: largura,
      height: altura,
      tzDate,
      legend: { show: false },
      cursor: compacto ? { show: false } : { y: false },
      padding: [6, 4, 0, 0],
      scales: {
        x: {
          time: true,
          range: () => {
            const agora = Date.now() / 1000;
            return [agora - janela.current, agora];
          },
        },
        y: { range: faixaY },
      },
      axes: eixos(cores, compacto),
      series: [serieTempo, { label: "BPM", stroke: cores.linha, width: 2, fill: cores.faixa, points: { show: false } }],
    }),
    dados,
    [pulseiraId, altura, compacto, cores.linha, cores.eixo],
  );

  useEffect(() => {
    let quadro = 0;
    const agendar = () => {
      if (quadro) return;
      quadro = requestAnimationFrame(() => {
        quadro = 0;
        plot.current?.setData(dados());
      });
    };
    agendar();
    const cancelar = aoVivo.assinarPontos(pulseiraId, agendar);
    const deslizar = setInterval(agendar, 1000); // a janela anda mesmo sem leituras novas
    return () => {
      cancelar();
      clearInterval(deslizar);
      cancelAnimationFrame(quadro);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pulseiraId, janelaS, plot]);

  return <div ref={ref} style={{ width: "100%", height: altura }} />;
}

export type PontoHistorico = { t: number; medio: number; min: number; max: number };

/** Histórico agregado: faixa mínimo–máximo e linha da média. */
export function GraficoBpmHistorico({
  pontos,
  de,
  ate,
  altura = 260,
}: {
  pontos: PontoHistorico[];
  de: number;
  ate: number;
  altura?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cores = useCores();
  const dados = (): uPlot.AlignedData => [
    pontos.map((p) => p.t),
    pontos.map((p) => p.max),
    pontos.map((p) => p.min),
    pontos.map((p) => p.medio),
  ];
  useUplot(
    ref,
    altura,
    (largura) => ({
      width: largura,
      height: altura,
      tzDate,
      cursor: { y: false },
      scales: { x: { time: true, range: () => [de, ate] }, y: { range: faixaY } },
      axes: eixos(cores, false),
      series: [
        serieTempo,
        { label: "Máximo", stroke: "transparent", points: { show: false } },
        { label: "Mínimo", stroke: "transparent", points: { show: false } },
        {
          label: "Média",
          stroke: cores.linha,
          width: 2,
          points: { show: false },
          value: (_u, v) => (v == null ? "—" : v.toFixed(0)),
        },
      ],
      bands: [{ series: [1, 2], fill: cores.faixa }],
    }),
    dados,
    [pontos, de, ate, altura, cores.linha, cores.eixo],
  );
  return <div ref={ref} style={{ width: "100%" }} />;
}
