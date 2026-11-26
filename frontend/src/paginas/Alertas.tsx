import { Alert, Anchor, Badge, Button, Group, Loader, SegmentedControl, Table, Text, Title, Tooltip } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAgora } from "../aoVivo/AoVivoProvider";
import { useAlertas, useReconhecer } from "../api/alertas";
import { descreverAlerta, duracao, TIPOS_ALERTA } from "../util/alertas";
import { formatarDataHora } from "../util/tempo";

export function Alertas() {
  useAgora();
  const [filtro, setFiltro] = useState("abertos");
  const { data, isLoading, error } = useAlertas(filtro === "abertos" ? { abertos: true } : {});
  const reconhecer = useReconhecer();

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Alertas</Title>
        <SegmentedControl
          value={filtro}
          onChange={setFiltro}
          data={[
            { value: "abertos", label: "Em andamento" },
            { value: "todos", label: "Todos" },
          ]}
        />
      </Group>

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.length === 0 && (
        <Text c="dimmed">{filtro === "abertos" ? "Nenhum alerta em andamento." : "Nenhum alerta registrado."}</Text>
      )}

      {data && data.length > 0 && (
        <Table.ScrollContainer minWidth={820}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Tipo</Table.Th>
                <Table.Th>Pesquisador</Table.Th>
                <Table.Th>Pulseira</Table.Th>
                <Table.Th>Detalhe</Table.Th>
                <Table.Th>Início</Table.Th>
                <Table.Th>Duração</Table.Th>
                <Table.Th>Reconhecido</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((a) => (
                <Table.Tr key={a.id}>
                  <Table.Td>
                    <Badge color={TIPOS_ALERTA[a.tipo].cor} variant={a.fim ? "light" : "filled"}>
                      {TIPOS_ALERTA[a.tipo].rotulo}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{a.pesquisador}</Table.Td>
                  <Table.Td>
                    <Anchor component={Link} to={`/pulseiras/${a.pulseira_id}`}>
                      {a.pulseira}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{descreverAlerta(a)}</Table.Td>
                  <Table.Td>{formatarDataHora(a.inicio)}</Table.Td>
                  <Table.Td>
                    {a.fim ? (
                      <Tooltip label={`Fim: ${formatarDataHora(a.fim)}`}>
                        <span>{duracao(a.inicio, a.fim)}</span>
                      </Tooltip>
                    ) : (
                      <Badge color="red" variant="dot">
                        em andamento · {duracao(a.inicio)}
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {a.reconhecido_em ? (
                      formatarDataHora(a.reconhecido_em)
                    ) : a.fim ? (
                      <Text c="dimmed" size="sm">
                        não
                      </Text>
                    ) : (
                      <Button
                        size="compact-xs"
                        variant="light"
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
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </>
  );
}
