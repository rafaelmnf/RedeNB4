import { Badge, Card, Group, Stack, Text, Tooltip } from "@mantine/core";
import { Link } from "react-router-dom";

import { useAgora, useAlertasAbertos } from "../aoVivo/AoVivoProvider";
import type { Cartao } from "../api/cliente";
import { TIPOS_ALERTA } from "../util/alertas";
import { formatarDataHora, haQuantoTempo } from "../util/tempo";
import { GraficoBpmAoVivo } from "./GraficoBpm";

export type EstadoCartao = "sem_dados" | "offline" | "fora_do_braco" | "online";

export function estadoDoCartao(c: Cartao): EstadoCartao {
  if (c.sem_dados) return "sem_dados";
  if (!c.online) return "offline";
  if (c.fora_do_braco) return "fora_do_braco";
  return "online";
}

export function BadgeEstado({ c }: { c: Cartao }) {
  switch (estadoDoCartao(c)) {
    case "sem_dados":
      return (
        <Badge color="gray" variant="light">
          sem dados
        </Badge>
      );
    case "offline":
      return <Badge color="gray">sem sinal</Badge>;
    case "fora_do_braco":
      return <Badge color="yellow">fora do braço</Badge>;
    default:
      return <Badge color="green">online</Badge>;
  }
}

function Info({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">
        {rotulo}
      </Text>
      <Text size="sm">{valor}</Text>
    </Stack>
  );
}

/** Card ao vivo de uma pulseira: quem está usando, BPM grande, gráfico e sinal.
 * Fica vermelho com alerta aberto, cinza quando está sem sinal e amarelo quando fora do
 * braço (nessa ordem de prioridade). */
export function CardPulseira({ c, janelaS, link = true }: { c: Cartao; janelaS: number; link?: boolean }) {
  useAgora();
  const alertas = useAlertasAbertos().filter((a) => a.pulseira_id === c.pulseira_id);
  const emAlerta = alertas.length > 0;
  const estado = estadoDoCartao(c);
  const apagado = !emAlerta && (estado === "offline" || estado === "sem_dados");
  const corBorda = emAlerta
    ? "var(--mantine-color-red-6)"
    : estado === "fora_do_braco"
      ? "var(--mantine-color-yellow-5)"
      : undefined;
  const subtitulo = c.apelido ? `${c.apelido} · ${c.mac}` : c.mac;

  const conteudo = (
    <Card
      withBorder
      radius="md"
      padding="md"
      style={{
        borderColor: corBorda,
        borderWidth: corBorda ? 2 : undefined,
        background: emAlerta
          ? "var(--mantine-color-red-light)"
          : apagado
            ? "var(--mantine-color-default-hover)"
            : undefined,
        opacity: apagado ? 0.75 : 1,
        height: "100%",
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
        <Stack gap={0} style={{ minWidth: 0 }}>
          <Text fw={700} truncate c={c.pesquisador ? undefined : "dimmed"} fs={c.pesquisador ? undefined : "italic"}>
            {c.pesquisador ?? "Não vinculada"}
          </Text>
          <Text size="xs" c="dimmed" truncate>
            {subtitulo}
          </Text>
        </Stack>
        <BadgeEstado c={c} />
      </Group>
      {emAlerta && (
        <Group gap={4} mt={6}>
          {alertas.map((a) => (
            <Badge key={a.id} color={TIPOS_ALERTA[a.tipo].cor} variant={a.reconhecido_em ? "light" : "filled"}>
              {TIPOS_ALERTA[a.tipo].rotulo}
              {a.reconhecido_em ? " (visto)" : ""}
            </Badge>
          ))}
        </Group>
      )}

      <Group align="baseline" gap={6} mt="xs">
        <Text fz={44} fw={700} lh={1} c={emAlerta ? "red" : apagado ? "dimmed" : undefined} style={{ fontVariantNumeric: "tabular-nums" }}>
          {c.ultimo_bpm ?? "—"}
        </Text>
        <Text size="sm" c="dimmed">
          BPM
        </Text>
      </Group>

      <GraficoBpmAoVivo pulseiraId={c.pulseira_id} janelaS={janelaS} />

      <Group gap="lg" mt="xs" wrap="nowrap">
        <Info rotulo="RSSI" valor={c.rssi != null ? `${Math.round(c.rssi)} dBm` : "—"} />
        <Info rotulo="Distância" valor={c.distancia_m != null ? `~${c.distancia_m.toFixed(1)} m` : "—"} />
        <Info rotulo="AP" valor={c.ap ?? "—"} />
        <Tooltip label={formatarDataHora(c.ultimo_contato)}>
          <div>
            <Info
              rotulo={estado === "offline" ? "Sem sinal" : "Último contato"}
              valor={haQuantoTempo(c.ultimo_contato)}
            />
          </div>
        </Tooltip>
      </Group>
    </Card>
  );

  if (!link) return conteudo;
  return (
    <Link to={`/pulseiras/${c.pulseira_id}`} style={{ textDecoration: "none", color: "inherit" }}>
      {conteudo}
    </Link>
  );
}
