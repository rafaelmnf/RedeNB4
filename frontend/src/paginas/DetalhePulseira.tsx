import { Alert, Anchor, Card, Group, Loader, SegmentedControl, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useCartao } from "../aoVivo/AoVivoProvider";
import { api, type Pulseira, type SerieBpm } from "../api/cliente";
import { CardPulseira } from "../componentes/CardPulseira";
import { GraficoBpmAoVivo, GraficoBpmHistorico } from "../componentes/GraficoBpm";
import { HistoricoVinculos } from "../componentes/HistoricoVinculos";

const PERIODOS = [
  { value: "1", label: "1 hora" },
  { value: "24", label: "24 horas" },
];

function useSerie(pulseiraId: number, horas: number) {
  return useQuery({
    queryKey: ["leituras", pulseiraId, horas],
    queryFn: () => {
      const de = new Date(Date.now() - horas * 3600_000).toISOString();
      return api<SerieBpm>(`/api/leituras?pulseira_id=${pulseiraId}&de=${encodeURIComponent(de)}`);
    },
    refetchInterval: 30_000,
  });
}

function Historico({ pulseiraId }: { pulseiraId: number }) {
  const [horas, setHoras] = useState("1");
  const { data, isLoading, error } = useSerie(pulseiraId, Number(horas));
  return (
    <Card withBorder radius="md">
      <Group justify="space-between" mb="sm">
        <Title order={4}>Histórico de BPM</Title>
        <SegmentedControl size="xs" data={PERIODOS} value={horas} onChange={setHoras} />
      </Group>
      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.pontos.length === 0 && <Text c="dimmed">Nenhuma leitura neste período.</Text>}
      {data && data.pontos.length > 0 && (
        <>
          <GraficoBpmHistorico
            pontos={data.pontos.map((p) => ({
              t: Date.parse(p.ts) / 1000,
              medio: p.bpm_medio,
              min: p.bpm_min,
              max: p.bpm_max,
            }))}
            de={Date.parse(data.de) / 1000}
            ate={Date.parse(data.ate) / 1000}
          />
          <Text size="xs" c="dimmed" mt={4}>
            Linha: média a cada {data.passo_s < 60 ? `${data.passo_s} s` : `${data.passo_s / 60} min`}. Faixa: mínimo
            e máximo no intervalo.
          </Text>
        </>
      )}
    </Card>
  );
}

export function DetalhePulseira() {
  const id = Number(useParams().id);
  const cartao = useCartao(id);
  const pulseira = useQuery({
    queryKey: ["pulseiras", id],
    queryFn: () => api<Pulseira>(`/api/pulseiras/${id}`),
    enabled: Number.isFinite(id),
  });

  if (!Number.isFinite(id)) return <Alert color="red">Pulseira inválida.</Alert>;
  if (pulseira.error) return <Alert color="red">{pulseira.error.message}</Alert>;
  const nome = pulseira.data?.apelido ?? pulseira.data?.mac ?? cartao?.nome ?? `Pulseira ${id}`;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{nome}</Title>
        <Anchor component={Link} to="/" size="sm">
          ← Dashboard
        </Anchor>
      </Group>

      {cartao ? (
        <>
          <CardPulseira c={cartao} janelaS={300} link={false} />
          <Card withBorder radius="md">
            <Title order={4} mb="sm">
              Ao vivo (últimos 15 min)
            </Title>
            <GraficoBpmAoVivo pulseiraId={id} janelaS={900} altura={220} compacto={false} />
          </Card>
        </>
      ) : (
        pulseira.data && (
          <Alert color="gray" title="Pulseira inativa">
            Esta pulseira está desativada, então não há dados ao vivo. O histórico continua disponível.
          </Alert>
        )
      )}

      <Historico pulseiraId={id} />

      <Card withBorder radius="md">
        <Title order={4} mb="sm">
          Quem usou esta pulseira
        </Title>
        <HistoricoVinculos pulseiraId={id} />
      </Card>
    </Stack>
  );
}
