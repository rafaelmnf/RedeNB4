import { Alert, Anchor, Badge, Button, Group, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconAlertTriangle } from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { useAgora, useAlertasAbertos } from "../aoVivo/AoVivoProvider";
import { useReconhecer } from "../api/alertas";
import { descreverAlerta, duracao, TIPOS_ALERTA } from "../util/alertas";

/** Alertas abertos no topo de todas as páginas. Os não reconhecidos ficam em destaque,
 * com o botão Reconhecer; os já reconhecidos aparecem resumidos até a condição acabar. */
export function BannerAlertas() {
  useAgora();
  const abertos = useAlertasAbertos();
  const reconhecer = useReconhecer();
  const pendentes = abertos.filter((a) => !a.reconhecido_em);
  const vistos = abertos.length - pendentes.length;
  if (abertos.length === 0) return null;

  return (
    <Stack gap="xs" mb="md">
      {pendentes.length > 0 && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle />} title={`${pendentes.length} alerta(s)`}>
          <Stack gap={6}>
            {pendentes.map((a) => (
              <Group key={a.id} justify="space-between" wrap="nowrap" gap="sm">
                <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                  <Badge color={TIPOS_ALERTA[a.tipo].cor} style={{ flexShrink: 0 }}>
                    {TIPOS_ALERTA[a.tipo].rotulo}
                  </Badge>
                  <Text size="sm" truncate>
                    <Anchor component={Link} to={`/pulseiras/${a.pulseira_id}`} fw={600}>
                      {a.pesquisador}
                    </Anchor>{" "}
                    ({a.pulseira}) · {descreverAlerta(a)} · há {duracao(a.inicio)}
                  </Text>
                </Group>
                <Button
                  size="compact-sm"
                  variant="white"
                  color="red"
                  loading={reconhecer.isPending && reconhecer.variables === a.id}
                  onClick={() =>
                    reconhecer.mutate(a.id, {
                      onError: (e) => notifications.show({ color: "red", title: "Erro", message: e.message }),
                    })
                  }
                >
                  Reconhecer
                </Button>
              </Group>
            ))}
          </Stack>
        </Alert>
      )}
      {vistos > 0 && (
        <Text size="sm" c="dimmed">
          {vistos} alerta(s) reconhecido(s) ainda em andamento ·{" "}
          <Anchor component={Link} to="/alertas" size="sm">
            ver alertas
          </Anchor>
        </Text>
      )}
    </Stack>
  );
}
