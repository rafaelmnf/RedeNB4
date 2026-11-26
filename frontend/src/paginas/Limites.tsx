import { Alert, Button, Card, Group, Loader, NumberInput, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useEffect, useState } from "react";

import { useLimites, useSalvarLimites } from "../api/alertas";
import type { LimitesEntrada } from "../api/cliente";
import { formatarDataHora } from "../util/tempo";

type Campo = { chave: keyof LimitesEntrada; rotulo: string; ajuda: string; min: number; max: number; sufixo: string };

const CAMPOS: Campo[] = [
  { chave: "bpm_min", rotulo: "BPM mínimo", ajuda: "Abaixo disso conta como BPM baixo.", min: 20, max: 250, sufixo: " BPM" },
  { chave: "bpm_max", rotulo: "BPM máximo", ajuda: "Acima disso conta como BPM alto.", min: 30, max: 250, sufixo: " BPM" },
  {
    chave: "duracao_s",
    rotulo: "Tempo fora da faixa",
    ajuda: "Por quanto tempo seguido o BPM precisa ficar fora da faixa para alertar.",
    min: 5,
    max: 3600,
    sufixo: " s",
  },
  {
    chave: "sem_sinal_s",
    rotulo: "Sem sinal",
    ajuda: "Alerta quando uma pulseira vinculada fica esse tempo sem enviar nada.",
    min: 5,
    max: 3600,
    sufixo: " s",
  },
  {
    chave: "fora_do_braco_s",
    rotulo: "Fora do braço",
    ajuda: "Alerta quando uma pulseira vinculada marca BPM 0 (fora do braço) por esse tempo.",
    min: 5,
    max: 3600,
    sufixo: " s",
  },
];

export function Limites() {
  const { data, isLoading, error } = useLimites();
  const salvar = useSalvarLimites();
  const [valores, setValores] = useState<LimitesEntrada | undefined>();

  useEffect(() => {
    if (data) setValores(data);
  }, [data]);

  const faixaInvalida = !!valores && valores.bpm_min >= valores.bpm_max;

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!valores || faixaInvalida) return;
    try {
      await salvar.mutateAsync(valores);
      notifications.show({ color: "green", message: "Limites salvos. Já valem para as próximas leituras." });
    } catch (e) {
      notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
    }
  }

  return (
    <Stack maw={720}>
      <Title order={2}>Limites dos alertas</Title>
      <Text c="dimmed" size="sm">
        Valem para todas as pulseiras vinculadas a alguém. Pulseiras sem ninguém não geram alerta.
      </Text>
      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {valores && (
        <Card withBorder radius="md" component="form" onSubmit={enviar}>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {CAMPOS.map((c) => (
              <NumberInput
                key={c.chave}
                label={c.rotulo}
                description={c.ajuda}
                min={c.min}
                max={c.max}
                suffix={c.sufixo}
                allowDecimal={false}
                required
                value={valores[c.chave]}
                onChange={(v) => setValores({ ...valores, [c.chave]: typeof v === "number" ? v : c.min })}
                error={faixaInvalida && (c.chave === "bpm_min" || c.chave === "bpm_max") ? "Mínimo deve ser menor que o máximo" : null}
              />
            ))}
          </SimpleGrid>
          <Group justify="space-between" mt="md">
            <Text size="xs" c="dimmed">
              Última alteração: {formatarDataHora(data?.atualizado_em)}
            </Text>
            <Button type="submit" loading={salvar.isPending} disabled={faixaInvalida}>
              Salvar
            </Button>
          </Group>
        </Card>
      )}
    </Stack>
  );
}
